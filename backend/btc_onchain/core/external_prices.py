from __future__ import annotations
import asyncio, time, math, random
import aiosqlite
import httpx
from typing import Dict, List, Optional, Tuple

class ExternalPricePoller:
    """
    Polls public BTC-USD price APIs on a schedule, persists to SQLite, and
    keeps a small in-memory snapshot of the latest prices by source + median.
    """

    def __init__(self, db_path: str, interval_s: float, sources: List[str]) -> None:
        self.db_path = db_path
        self.interval_s = max(5.0, float(interval_s))
        self.sources = [s.strip().lower() for s in sources if s.strip()]
        self._task: Optional[asyncio.Task] = None
        self._stop_evt = asyncio.Event()
        self.latest: Dict[str, float] = {}      # per-source latest
        self.latest_ts: Dict[str, float] = {}   # per-source timestamp
        self.latest_median: Optional[float] = None
        self.latest_median_ts: Optional[float] = None
        self._client: Optional[httpx.AsyncClient] = None
        self._lock = asyncio.Lock()

    # ---------- lifecycle ----------

    async def start(self) -> None:
        await self._init_db()
        if self._client is None:
            self._client = httpx.AsyncClient(timeout=httpx.Timeout(6.0, connect=3.0, read=4.0))
        if self._task is None or self._task.done():
            self._stop_evt.clear()
            self._task = asyncio.create_task(self._run(), name="ext-price-poller")

    async def stop(self) -> None:
        self._stop_evt.set()
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except Exception:
                pass
        if self._client:
            await self._client.aclose()
        self._client = None

    # ---------- public API ----------

    async def history(self, limit: int = 200) -> List[Tuple[float, str, float]]:
        """
        Returns rows: (ts, source, price), newest first.
        """
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            cur = await db.execute("""
                SELECT ts, source, price
                FROM prices
                ORDER BY ts DESC
                LIMIT ?
            """, (int(limit),))
            rows = await cur.fetchall()
        return [(float(r["ts"]), str(r["source"]), float(r["price"])) for r in rows]

    def snapshot(self) -> dict:
        """
        Latest values (non-blocking).
        """
        # make a shallow copy under lock for consistency
        async def _copy():
            async with self._lock:
                return {
                    "t": time.time(),
                    "sources": {k: {"price": v, "ts": self.latest_ts.get(k)} for k, v in self.latest.items()},
                    "median": {"price": self.latest_median, "ts": self.latest_median_ts},
                }
        # If called from sync context, that's OK—return best-effort
        try:
            loop = asyncio.get_running_loop()
            return loop.run_until_complete(_copy())
        except RuntimeError:
            # no loop
            return {
                "t": time.time(),
                "sources": {k: {"price": v, "ts": self.latest_ts.get(k)} for k, v in self.latest.items()},
                "median": {"price": self.latest_median, "ts": self.latest_median_ts},
            }

    # ---------- internals ----------

    async def _init_db(self) -> None:
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute("""
                CREATE TABLE IF NOT EXISTS prices(
                    ts REAL NOT NULL,
                    source TEXT NOT NULL,
                    price REAL NOT NULL
                )
            """)
            await db.execute("CREATE INDEX IF NOT EXISTS idx_prices_ts ON prices(ts DESC)")
            await db.commit()

    async def _run(self) -> None:
        # Stagger first run slightly
        await asyncio.sleep(0.1 + random.random() * 0.4)
        while not self._stop_evt.is_set():
            t0 = time.time()
            try:
                await self._tick()
            except Exception:
                # swallow, keep polling
                pass
            # sleep with jitter to avoid accidental sync with other jobs
            elapsed = time.time() - t0
            sleep_s = max(1.0, self.interval_s - elapsed) * (0.85 + 0.3 * random.random())
            try:
                await asyncio.wait_for(self._stop_evt.wait(), timeout=sleep_s)
            except asyncio.TimeoutError:
                pass

    async def _tick(self) -> None:
        if not self.sources:
            return
        assert self._client is not None
        client = self._client

        async def _fetch_one(src: str) -> Optional[float]:
            # Return a float price or None on failure
            try:
                if src == "coinbase":
                    r = await client.get("https://api.exchange.coinbase.com/products/BTC-USD/ticker")
                    r.raise_for_status()
                    j = r.json()
                    return float(j["price"])
                if src == "bitstamp":
                    r = await client.get("https://www.bitstamp.net/api/v2/ticker/btcusd/")
                    r.raise_for_status()
                    j = r.json()
                    return float(j["last"])
                if src == "kraken":
                    r = await client.get("https://api.kraken.com/0/public/Ticker?pair=XBTUSD")
                    r.raise_for_status()
                    j = r.json()
                    data = j["result"]
                    # XBTUSD or XXBTZUSD depending on API
                    key = next(iter(data.keys()))
                    # 'c' => last trade [price, lot]
                    return float(data[key]["c"][0])
                if src == "bitfinex":
                    r = await client.get("https://api.bitfinex.com/v1/pubticker/btcusd")
                    r.raise_for_status()
                    j = r.json()
                    return float(j["last_price"])
                if src == "coingecko":
                    r = await client.get("https://api.coingecko.com/api/v3/simple/price?ids=bitcoin&vs_currencies=usd")
                    r.raise_for_status()
                    j = r.json()
                    return float(j["bitcoin"]["usd"])
                return None
            except Exception:
                return None

        # Fetch in parallel with modest fanout
        tasks = [asyncio.create_task(_fetch_one(s)) for s in self.sources]
        results = await asyncio.gather(*tasks, return_exceptions=False)
        ts = time.time()

        rows: List[Tuple[float, str, float]] = []
        ok_prices: List[float] = []
        for src, val in zip(self.sources, results):
            if val is None or not math.isfinite(val) or val <= 0:
                continue
            rows.append((ts, src, float(val)))
            ok_prices.append(float(val))

        if not rows:
            return

        # Persist
        async with aiosqlite.connect(self.db_path) as db:
            await db.executemany("INSERT INTO prices(ts, source, price) VALUES (?, ?, ?)", rows)
            await db.commit()

        # Update snapshot
        median_price = None
        if ok_prices:
            ok_prices.sort()
            n = len(ok_prices)
            median_price = ok_prices[n // 2] if n % 2 == 1 else 0.5 * (ok_prices[n // 2 - 1] + ok_prices[n // 2])
        async with self._lock:
            for (ts_i, src_i, p_i) in rows:
                self.latest[src_i] = p_i
                self.latest_ts[src_i] = ts_i
            self.latest_median = median_price
            self.latest_median_ts = ts

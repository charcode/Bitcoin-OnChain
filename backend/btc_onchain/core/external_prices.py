"""Exchange quotes for evaluation only; never imported by estimator modules."""
import asyncio
import datetime as dt
import math
import statistics
import time
import aiosqlite
import httpx


class ExternalPricePoller:
    def __init__(self, db_path, interval_s, sources):
        self.db_path = db_path
        self.interval_s = max(10., float(interval_s))
        self.sources = list(dict.fromkeys(s.strip().lower() for s in sources))
        self.quotes = {}
        self._task = None
        self._client = None

    async def start(self):
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute('CREATE TABLE IF NOT EXISTS prices(ts REAL NOT NULL, source TEXT NOT NULL, price REAL NOT NULL)')
            await db.execute('CREATE INDEX IF NOT EXISTS idx_prices_ts ON prices(ts DESC)')
            await db.commit()
        self._client = httpx.AsyncClient(timeout=8.)
        self._task = asyncio.create_task(self._run())

    async def stop(self):
        if self._task:
            self._task.cancel()
            try: await self._task
            except asyncio.CancelledError: pass
        if self._client: await self._client.aclose()

    async def _fetch(self, source):
        urls = {
            'kraken': 'https://api.kraken.com/0/public/Ticker?pair=XBTUSD',
            'coinbase': 'https://api.exchange.coinbase.com/products/BTC-USD/ticker',
            'bitstamp': 'https://www.bitstamp.net/api/v2/ticker/btcusd/',
        }
        if source not in urls:
            return source, {'status': 'unsupported', 'price': None, 'quote_currency': 'USD'}
        try:
            response = await self._client.get(urls[source]); response.raise_for_status()
            body = response.json(); observed = time.time(); market_ts = None
            if source == 'kraken':
                if body.get('error'): raise ValueError('Exchange error')
                price = float(next(iter(body['result'].values()))['c'][0])
            elif source == 'coinbase':
                price = float(body['price'])
                market_ts = dt.datetime.fromisoformat(body['time'].replace('Z', '+00:00')).timestamp()
            else:
                price = float(body['last']); market_ts = float(body['timestamp'])
            if not math.isfinite(price) or price <= 0: raise ValueError('Invalid price')
            return source, {'status': 'ok', 'price': price, 'ts': observed,
                'market_ts': market_ts, 'quote_currency': 'USD', 'timestamp_kind': 'trade' if source == 'coinbase' else 'retrieval_or_snapshot'}
        except Exception:
            return source, {**self.quotes.get(source, {}), 'status': 'unavailable', 'quote_currency': 'USD'}

    async def _tick(self):
        self.quotes = dict(await asyncio.gather(*(self._fetch(s) for s in self.sources)))
        rows = [(q['ts'], s, q['price']) for s,q in self.quotes.items() if q.get('status') == 'ok']
        async with aiosqlite.connect(self.db_path) as db:
            await db.executemany('INSERT INTO prices VALUES (?,?,?)', rows)
            await db.execute('DELETE FROM prices WHERE ts < ?', (time.time() - 14*86400,))
            await db.commit()

    async def _run(self):
        while True:
            try: await self._tick()
            except Exception: pass
            await asyncio.sleep(self.interval_s)

    def snapshot(self, now=None):
        now = time.time() if now is None else now
        sources = {}
        good = []
        for name in self.sources:
            q = dict(self.quotes.get(name, {'status': 'warming_up', 'price': None, 'quote_currency': 'USD'}))
            age = now-q['ts'] if q.get('ts') else None
            market_age = now-q['market_ts'] if q.get('market_ts') else None
            q['age_sec'] = age
            q['market_age_sec'] = market_age
            q['fresh'] = q.get('status') == 'ok' and age is not None and 0 <= age <= 90 and (market_age is None or -5 <= market_age <= 120)
            sources[name] = q
            if q['fresh']: good.append(q)
        median = statistics.median(q['price'] for q in good) if good else None
        return {'t': now, 'sources': sources, 'median': {'price': median,
            'ts': min(q['ts'] for q in good) if good else None, 'source_count': len(good), 'quote_currency': 'USD'}}

    async def history(self, limit=200):
        async with aiosqlite.connect(self.db_path) as db:
            rows = await (await db.execute('SELECT ts,source,price FROM prices ORDER BY ts DESC LIMIT ?', (limit,))).fetchall()
        return rows

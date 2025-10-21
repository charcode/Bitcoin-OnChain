from __future__ import annotations

import asyncio
import json
import logging
import ssl
import time
from typing import Any, Dict, Optional, Tuple, List

logger = logging.getLogger(__name__)


class FulcrumClient:
    """
    Minimal persistent Electrum/Fulcrum JSON-RPC client with:
      - One TCP connection kept open.
      - Background reader that demuxes responses to awaiting Futures.
      - Large read buffer (handles very large JSON frames).
      - Graceful handling of SSL 'close-notify'.
      - Simple per-height tx cache and bounded concurrency.
    """

    def __init__(
        self,
        host: str,
        port: int,
        use_ssl: bool = True,
        verify_ssl: bool = False,
        request_timeout: float = 30.0,
        max_line_bytes: int = 16 * 1024 * 1024,  # 16 MiB safety for big JSON
    ) -> None:
        # Config
        self._host = host
        self._port = int(port)
        self._use_ssl = bool(use_ssl)
        self._request_timeout = float(request_timeout)
        self._max_line = int(max_line_bytes)

        # SSL context (optional verification)
        self._ssl_context: Optional[ssl.SSLContext] = None
        if self._use_ssl:
            ctx = ssl.create_default_context()
            if not verify_ssl:
                ctx.check_hostname = False
                ctx.verify_mode = ssl.CERT_NONE
            self._ssl_context = ctx

        # IO state
        self._reader: Optional[asyncio.StreamReader] = None
        self._writer: Optional[asyncio.StreamWriter] = None
        self._read_task: Optional[asyncio.Task] = None
        self._lock = asyncio.Lock()  # serializes writes & (re)connects
        self._closed = False

        # JSON-RPC plumbing
        self._next_id = 0
        self._pending: Dict[int, asyncio.Future] = {}

        # Capabilities / diagnostics
        self._caps_checked = False
        self._server_version: Optional[str] = None
        self._last_negotiate_error: Optional[str] = None

        # Per-height cache for get_block_transactions()
        self._tx_cache: Dict[int, Tuple[List[dict], float]] = {}
        self._cache_ttl = 180.0  # seconds

        # Concurrency guards
        self._tx_sem = asyncio.Semaphore(20)
        self._idfrompos_sem = asyncio.Semaphore(80)

    # ---------- public lifecycle ----------

    async def aclose(self) -> None:
        """Close connection and stop reader task."""
        self._closed = True
        # Cancel reader task
        try:
            if self._read_task and not self._read_task.done():
                self._read_task.cancel()
                with contextlib.suppress(Exception):
                    await self._read_task
        except Exception:
            pass
        # Close streams
        await self._shutdown_streams()
        # Fail any pending futures
        for fid, fut in list(self._pending.items()):
            if not fut.done():
                fut.set_exception(ConnectionError("fulcrum client closed"))
        self._pending.clear()

    # ---------- connection & reader ----------

    async def _ensure_connected(self) -> None:
        if self._reader and not self._reader.at_eof() and self._writer:
            return
        await self._connect()

    async def _connect(self) -> None:
        async with self._lock:
            if self._reader and not self._reader.at_eof() and self._writer:
                return
            await self._shutdown_streams()
            logger.info(f"FulcrumClient: connecting to {self._host}:{self._port} (ssl={self._use_ssl})")
            reader, writer = await asyncio.open_connection(
                host=self._host,
                port=self._port,
                ssl=self._ssl_context,
                # Big per-line limit to avoid LimitOverrunError on large JSON
                limit=self._max_line,
            )
            self._reader, self._writer = reader, writer
            # Start background reader
            self._read_task = asyncio.create_task(self._read_loop(), name="fulcrum-read-loop")
            # Reset negotiation on new connection
            self._caps_checked = False
            self._server_version = None
            self._last_negotiate_error = None

    async def _shutdown_streams(self) -> None:
        rd, wr = self._reader, self._writer
        self._reader = None
        self._writer = None
        if wr is not None:
            try:
                wr.close()
                try:
                    await wr.wait_closed()
                except ssl.SSLError:
                    # Quiet close-notify noise
                    pass
                except Exception:
                    pass
            except Exception:
                pass

    async def _read_loop(self) -> None:
        """
        Reads '\n'-delimited JSON-RPC responses and dispatches them to pending Futures.
        Reconnects automatically on errors (unless explicitly closed).
        """
        try:
            assert self._reader is not None
            reader = self._reader
            while not self._closed:
                # Using explicit readuntil; limit was raised in open_connection.
                line = await reader.readuntil(b"\n")
                if not line:
                    # Peer closed
                    raise ConnectionError("fulcrum: peer closed")
                try:
                    obj = json.loads(line.decode("utf-8", errors="replace"))
                except Exception as e:
                    logger.warning(f"FulcrumClient: JSON decode error: {e!r}")
                    continue

                # Electrum server may send list (batch) or dict
                if isinstance(obj, list):
                    for entry in obj:
                        await self._dispatch(entry)
                else:
                    await self._dispatch(obj)

        except (asyncio.CancelledError, GeneratorExit):
            # Normal shutdown path
            pass
        except (asyncio.LimitOverrunError, ValueError) as e:
            # Framing exceeded limit or malformed line; reconnect.
            logger.error(f"FulcrumClient: read loop framing error: {e!r}; reconnecting")
        except Exception as e:
            # Connection / SSL errors, etc.
            logger.warning(f"FulcrumClient: read loop error: {e!r}; reconnecting")
        finally:
            # Fail all pending futures on disconnect
            for fid, fut in list(self._pending.items()):
                if not fut.done():
                    fut.set_exception(ConnectionError("fulcrum connection lost"))
            self._pending.clear()
            # Close streams
            await self._shutdown_streams()
            # Auto-reconnect if not explicitly closed
            if not self._closed:
                try:
                    await asyncio.sleep(0.5)
                    await self._connect()
                except Exception as e:
                    logger.error(f"FulcrumClient: reconnect failed: {e!r}")

    async def _dispatch(self, obj: Any) -> None:
        """
        Dispatch a JSON-RPC response object to its awaiting Future.
        Accepts shapes: { "id": ..., "result": ... } or { "id": ..., "error": ... }.
        """
        if not isinstance(obj, dict) or "id" not in obj:
            return
        fid = obj.get("id")
        fut = self._pending.pop(fid, None)
        if fut is None:
            return
        if "error" in obj and obj["error"]:
            err = obj["error"]
            msg = err.get("message") if isinstance(err, dict) else str(err)
            if not fut.done():
                fut.set_exception(RuntimeError(msg))
        else:
            if not fut.done():
                fut.set_result(obj.get("result"))

    # ---------- JSON-RPC helpers ----------

    async def _rpc(self, method: str, params: Optional[list] = None, timeout: Optional[float] = None) -> Any:
        """
        Send a single JSON-RPC request and await result.
        """
        await self._ensure_connected()

        # Create future and send line atomically under lock
        async with self._lock:
            self._next_id += 1
            rid = self._next_id
            fut: asyncio.Future = asyncio.get_running_loop().create_future()
            self._pending[rid] = fut

            payload = {
                "jsonrpc": "2.0",
                "id": rid,
                "method": method,
                "params": params or [],
            }
            line = (json.dumps(payload) + "\n").encode("utf-8")
            assert self._writer is not None
            self._writer.write(line)
            await self._writer.drain()

        # Wait for result
        try:
            return await asyncio.wait_for(fut, timeout or self._request_timeout)
        except Exception:
            # Clean pending on error
            self._pending.pop(rid, None)
            raise

    async def _negotiate(self) -> None:
        """
        Probe server capabilities / version once per connection.
        """
        if self._caps_checked:
            return
        try:
            v = await self._rpc("server.version", ["btc-onchain", "1.4"], timeout=10)
            # v can be "Fulcrum 1.9.x" OR ["Fulcrum 1.9.x","1.5"]
            if isinstance(v, (list, tuple)) and v:
                self._server_version = str(v[0])
            else:
                self._server_version = str(v)
            self._last_negotiate_error = None
        except Exception as e:
            self._server_version = None
            self._last_negotiate_error = str(e)
        finally:
            self._caps_checked = True

    # ---------- Electrum methods used by the app ----------

    async def _block_header(self, height: int) -> Optional[str]:
        try:
            hdr = await self._rpc("blockchain.block.header", [height], timeout=15)
            return str(hdr) if hdr is not None else None
        except Exception:
            return None

    async def _id_from_pos(self, height: int, tx_pos: int) -> Optional[str]:
        """
        Ask for txid at (height, tx_pos). Returns None if out of range.
        """
        try:
            async with self._idfrompos_sem:
                res = await self._rpc("blockchain.transaction.id_from_pos", [height, tx_pos, False], timeout=15)
            return str(res) if res else None
        except Exception:
            return None

    async def _tx_get(self, txid: str, verbose: bool = True) -> Optional[dict]:
        """
        Get verbose transaction dict (Core-like shape with vout list).
        """
        try:
            async with self._tx_sem:
                res = await self._rpc("blockchain.transaction.get", [txid, verbose], timeout=self._request_timeout)
            return res if isinstance(res, dict) else None
        except Exception:
            return None

    # ---------- High-level helper for routes ----------

    async def get_block_transactions(self, height: int) -> List[dict]:
        """
        Returns a list of verbose tx dicts for a given block height.
        Uses id_from_pos to discover count, then fetches txs with moderate parallelism.
        """
        now = time.time()
        cached = self._tx_cache.get(height)
        if cached and (now - cached[1]) <= self._cache_ttl:
            return cached[0]

        await self._negotiate()

        # Ensure block exists
        hdr = await self._block_header(height)
        if hdr is None:
            raise RuntimeError(f"Fulcrum: cannot read block header at height {height}")

        # Exponential probe to find an upper bound for tx count
        step = 64
        hi = 0
        while True:
            res = await self._id_from_pos(height, hi)
            if res is None:
                break
            hi += step
            if hi > 500_000:  # hard safety bound
                break

        # Binary search exact n_tx in [0, hi)
        lo, up = 0, hi
        while lo < up:
            mid = (lo + up) // 2
            res = await self._id_from_pos(height, mid)
            if res is None:
                up = mid
            else:
                lo = mid + 1
        n_tx = lo
        if n_tx <= 0:
            txs: List[dict] = []
            self._tx_cache[height] = (txs, now)
            return txs

        # Gather txids
        async def get_txid(i: int) -> Optional[str]:
            return await self._id_from_pos(height, i)

        txid_tasks = [asyncio.create_task(get_txid(i)) for i in range(n_tx)]
        txids_all = await asyncio.gather(*txid_tasks, return_exceptions=False)
        txids: List[str] = [t for t in txids_all if isinstance(t, str)]

        # Fetch verbose tx dicts
        async def get_verbose(txid: str) -> Optional[dict]:
            return await self._tx_get(txid, verbose=True)

        tx_tasks = [asyncio.create_task(get_verbose(t)) for t in txids]
        txs_all = await asyncio.gather(*tx_tasks, return_exceptions=False)
        txs: List[dict] = [t for t in txs_all if isinstance(t, dict)]

        # Cache (bounded)
        self._tx_cache[height] = (txs, now)
        if len(self._tx_cache) > 64:
            oldest = min(self._tx_cache.keys(), key=lambda k: self._tx_cache[k][1])
            self._tx_cache.pop(oldest, None)
        return txs


# Small stdlib import used in aclose(); kept at bottom to avoid cluttering top.
import contextlib  # noqa: E402

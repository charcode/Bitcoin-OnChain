from __future__ import annotations
import time
import asyncio
import numpy as np
from .config import settings
from .rpc import Rpc
from . import state
from .rnr import rnr_search, weight_output
from .models import PriceEstimate

def _is_not_found(err: Exception) -> bool:
    try:
        e = err.args[0]
        return isinstance(e, dict) and e.get("code") == -5
    except Exception:
        return False

async def refresh_mempool(rpc: Rpc) -> None:
    mp = await rpc.call("getrawmempool", [True])
    now = time.time()
    cutoff = now - settings.lookback_sec

    # expire old outputs
    state.mempool_outputs = {k: v for k, v in state.mempool_outputs.items()
                             if v["first_seen"] >= cutoff}

    # new txids (we haven't stored any outputs for them)
    seen_txids = {txid for (txid, _) in state.mempool_outputs.keys()}
    new_txids = [txid for txid in mp.keys() if txid not in seen_txids]

    # cap decode work per tick
    budget = max(0, settings.decode_per_tick)
    if budget and len(new_txids) > budget:
        new_txids = new_txids[:budget]

    decoded = 0
    for i, txid in enumerate(new_txids):
        if i % 25 == 0:
            await asyncio.sleep(0)  # keep loop responsive

        fs = state.tx_first_seen.get(txid, now)
        state.tx_first_seen[txid] = fs
        if fs < cutoff:
            continue

        meta = mp.get(txid, {})
        try:
            raw = await rpc.call("getrawtransaction", [txid, True])
        except Exception as e:
            if _is_not_found(e):
                continue
            continue

        vout = raw.get("vout", [])
        is_rbf = (meta.get("bip125-replaceable") == "yes")
        w = weight_output(len(vout), is_rbf)

        for o in vout:
            n = o.get("n")
            if n is None:
                continue
            val = float(o.get("value", 0.0))
            state.mempool_outputs[(txid, n)] = {
                "value_btc": val,
                "first_seen": fs,
                "weight": w,
            }
        decoded += 1

    # heartbeat
    print(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] [refresh] "
          f"candidates={len(state.mempool_outputs):6d} "
          f"(decoded {decoded:4d}, budget {settings.decode_per_tick})")

async def refresh_loop(rpc: Rpc) -> None:
    while True:
        try:
            await refresh_mempool(rpc)
        except Exception as e:
            ts = time.strftime("%Y-%m-%d %H:%M:%S")
            print(f"[{ts}] [refresh error]: {e}")
        await asyncio.sleep(settings.poll_interval)

async def rnr_loop() -> None:
    """Compute RNR (price + curve) in a thread; cache results."""
    while True:
        try:
            outs = list(state.mempool_outputs.values())
            if len(outs) >= settings.min_samples:
                # Offload CPU-bound work
                p, score, curv, pts = await asyncio.to_thread(rnr_search, outs)

                # cache curve for the /rnr/curve endpoint
                state.last_curve_points = pts
                state.last_curve_ts = time.time()

                # confidence heuristic
                svals = [s for _, s in pts]
                peak_norm = (score / (np.mean(svals) + 1e-9)) if svals else 0.0
                conf = float(np.tanh(0.15 * peak_norm) * np.tanh(0.001 * curv + 1e-9))

                # EMA smoothing
                if state.ema_price is None:
                    state.ema_price = p
                else:
                    state.ema_price = settings.ema_alpha * p + (1 - settings.ema_alpha) * state.ema_price  # type: ignore

                state.latest_estimate = PriceEstimate(
                    t=time.time(),
                    price=float(state.ema_price or 0.0),
                    confidence=max(0.0, min(1.0, conf)),
                    curvature=float(curv),
                    samples_used=len(outs),
                )
        except Exception as e:
            ts = time.strftime("%Y-%m-%d %H:%M:%S")
            print(f"[{ts}] [rnr error]: {e}")
        await asyncio.sleep(settings.scan_interval)

from __future__ import annotations
import asyncio
import time
from typing import Optional

from fastapi import FastAPI, Query
from fastapi.middleware.cors import CORSMiddleware

from .config import SETTINGS
from .rpc import Rpc
from .state import AppState
from .types import CurveResp, CurvePoint, CandidatesInfo, HistogramResp
from .mempool import MempoolCache
from .rnr import rnr_histogram_usd


app = FastAPI(title="btc-onchain RNR Nowcaster", version="0.2.0")

# CORS for Vite dev server
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "http://localhost:4173",
        "http://127.0.0.1:4173",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

STATE: Optional[AppState] = None
TASKS: list[asyncio.Task] = []


@app.on_event("startup")
async def _startup():
    global STATE, TASKS
    rpc = Rpc(SETTINGS.btc_rpc_url, SETTINGS.btc_rpc_user, SETTINGS.btc_rpc_pass)
    STATE = AppState(rpc=rpc, mempool=MempoolCache())
    # spawn workers
    TASKS = [
        asyncio.create_task(STATE.refresh_loop(), name="mempool-refresh"),
        asyncio.create_task(STATE.rnr_loop(), name="rnr-loop"),
    ]


@app.on_event("shutdown")
async def _shutdown():
    global STATE, TASKS
    if STATE:
        STATE.stop_evt.set()
        try:
            await STATE.rpc.aclose()
        except Exception:
            pass
    for t in TASKS:
        t.cancel()


@app.get("/health")
async def health():
    return {"ok": True, "t": int(time.time())}


@app.get("/price/now")
async def price_now():
    assert STATE is not None
    return STATE.latest_price_now()


@app.get("/rnr/curve", response_model=CurveResp)
async def rnr_curve():
    assert STATE is not None
    res = STATE.rnr.last_result
    pts: list[CurvePoint] = []
    if res is not None:
        pts = [CurvePoint(p=p, s=z) for p, z in zip(res.grid_prices, res.zscores)]
    return CurveResp(t=int(time.time()), points=pts)


@app.get("/debug/candidates", response_model=CandidatesInfo)
async def debug_candidates():
    assert STATE is not None
    total = len(STATE.mempool.outputs)
    usable = len(STATE.mempool.get_recent_outputs())
    return CandidatesInfo(total_outputs_cached=total, usable=usable)


@app.get("/debug/histogram", response_model=HistogramResp)
async def debug_histogram(
    price: Optional[float] = Query(None, description="USD/BTC used to convert outputs; defaults to latest estimate"),
    step: Optional[float] = Query(None, description="Bucket size in USD; defaults to PRICE_STEP"),
):
    """
    Returns counts per round-dollar bucket for outputs converted to USD using `price`.
    """
    assert STATE is not None
    outs = STATE.mempool.get_recent_outputs()
    used_price = price or (STATE.rnr.last_result.best_price if STATE.rnr.last_result else None)
    used_price = float(used_price) if used_price else SETTINGS.price_min  # fallback to pmin
    used_step = float(step) if step else SETTINGS.price_step

    buckets = rnr_histogram_usd(outs, used_price, used_step, SETTINGS.price_min, SETTINGS.price_max)
    # stringify keys for JSON stability on the client side
    buckets_str = {f"{int(k) if k.is_integer() else k}": v for k, v in buckets.items()}
    return HistogramResp(
        t=int(time.time()),
        used_price=used_price,
        step=used_step,
        buckets=buckets_str,
        total_samples=len(outs),
    )

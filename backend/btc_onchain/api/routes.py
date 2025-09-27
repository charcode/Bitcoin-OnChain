from __future__ import annotations
import time
from typing import Optional
from fastapi import APIRouter, Query, Request

from ..models import PriceEstimate, CurveResp, CurvePoint, CandidatesInfo, HistogramResp, HistBin
from ..config import SETTINGS

router = APIRouter()


def _state(request: Request):
    return request.app.state.app_state  # set in main.py


@router.get("/health")
async def health():
    return {"ok": True, "t": int(time.time())}


@router.get("/price/now", response_model=PriceEstimate)
async def price_now(request: Request):
    st = _state(request)
    return st.latest_price_now()


@router.get("/rnr/curve", response_model=CurveResp)
async def rnr_curve(request: Request):
    st = _state(request)
    res = st.rnr.last_result
    pts = []
    if res:
        # NOTE: SearchResult exposes .scores (baseline-subtracted). Use that.
        pts = [CurvePoint(p=float(p), s=float(s)) for p, s in zip(res.grid_prices, res.scores)]
    return CurveResp(t=float(time.time()), points=pts)


@router.get("/debug/candidates", response_model=CandidatesInfo)
async def debug_candidates(request: Request):
    st = _state(request)
    total = len(st.mempool.outputs)
    usable = len(st.mempool.get_recent_outputs())
    return CandidatesInfo(total_outputs_cached=total, usable=usable)


@router.get("/debug/histogram", response_model=HistogramResp)
async def debug_histogram(
    request: Request,
    grid: int = Query(100, description="Round-dollar grid size (USD multiple)"),
    span: int = Query(SETTINGS.hist_span_mults, ge=1, le=50, description="± multiples around center"),
):
    st = _state(request)
    res = st.rnr.last_result
    used_price = float(res.best_price) if res else float(SETTINGS.price_min)
    half = SETTINGS.hist_sigma_frac * float(grid)
    bins_list = st.rnr.hist_cache.get(grid)

    # Compute on-demand if not yet cached
    if not bins_list:
        outs = st.mempool.get_recent_outputs()
        from ..rnr import rnr_histogram_usd
        bins_list = rnr_histogram_usd(outs, used_price, grid, span, half)

    return HistogramResp(
        t=float(time.time()),
        grid=int(grid),
        span=int(span),
        window=float(half),
        used_price=used_price,
        bins=[HistBin(**b) for b in bins_list][: 2 * span + 1],
        total_samples=len(st.mempool.get_recent_outputs()),
    )

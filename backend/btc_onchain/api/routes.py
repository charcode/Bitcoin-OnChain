from __future__ import annotations
import time
from fastapi import APIRouter
from .. import state
from ..models import PriceEstimate, CurveResponse, CurvePoint

router = APIRouter()

@router.get("/price/now", response_model=PriceEstimate)
async def price_now():
    return state.latest_estimate or PriceEstimate(
        t=time.time(), price=0.0, confidence=0.0, curvature=0.0, samples_used=0
    )

@router.get("/rnr/curve", response_model=CurveResponse)
async def rnr_curve():
    pts = state.last_curve_points or []
    return CurveResponse(
        t=state.last_curve_ts or time.time(),
        points=[CurvePoint(p=p, s=s) for p, s in pts],
    )

@router.get("/debug/candidates")
async def debug_candidates():
    total = len(state.mempool_outputs)
    usable = total
    return {"total_outputs_cached": total, "usable": usable}

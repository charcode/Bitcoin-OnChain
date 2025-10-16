from __future__ import annotations
import time
from fastapi import APIRouter, Request, Query, HTTPException
from ..config import SETTINGS

router = APIRouter()

def _state(request: Request):
    return request.app.state.app_state

@router.get("/external/price/sources")
async def ext_sources():
    return {"sources": [s.strip() for s in SETTINGS.external_prices_sources_csv.split(",") if s.strip()]}

@router.get("/external/price/now")
async def ext_price_now(request: Request):
    st = _state(request)
    poller = getattr(st, "ext_prices", None)
    if poller is None:
        raise HTTPException(status_code=503, detail="External price poller disabled")
    snap = poller.snapshot()
    return snap

@router.get("/external/price/history")
async def ext_price_history(request: Request, limit: int = Query(300, ge=1, le=5000)):
    st = _state(request)
    poller = getattr(st, "ext_prices", None)
    if poller is None:
        raise HTTPException(status_code=503, detail="External price poller disabled")
    rows = await poller.history(limit=limit)
    return {"rows": [{"ts": ts, "source": src, "price": price} for (ts, src, price) in rows]}

@router.get("/price/compare")
async def price_compare(request: Request):
    """
    Compare your nowcaster (/price/now) with the external median.
    """
    st = _state(request)
    # your nowcaster:
    now = st.latest_price_now()  # existing method in your code
    now_price = float(now.get("price", 0.0))

    poller = getattr(st, "ext_prices", None)
    ext = None
    if poller:
        snap = poller.snapshot()
        ext = snap.get("median", {})
    ext_price = float(ext.get("price") or 0.0)

    delta = None
    if ext_price > 0 and now_price > 0:
        delta = 100.0 * (now_price - ext_price) / ext_price

    return {
        "t": time.time(),
        "nowcaster": now,
        "external": {"price": ext_price, "ts": ext.get("ts") if ext else None},
        "delta_pct": delta,
    }

from fastapi import APIRouter, Request, Query, HTTPException
from ..config import SETTINGS
from ..core.evaluation import compare

router = APIRouter()

def _state(request): return request.app.state.app_state

@router.get('/external/price/sources')
async def ext_sources():
    return {'sources': SETTINGS.external_prices_sources}

@router.get('/external/price/now')
async def ext_price_now(request: Request):
    poller = getattr(_state(request), 'ext_prices', None)
    if poller is None: raise HTTPException(status_code=503, detail='External comparison disabled')
    return poller.snapshot()

@router.get('/external/price/history')
async def ext_price_history(request: Request, limit: int = Query(300, ge=1, le=5000)):
    poller = getattr(_state(request), 'ext_prices', None)
    if poller is None: raise HTTPException(status_code=503, detail='External comparison disabled')
    return {'rows': [{'ts': t, 'source': s, 'price': p} for t,s,p in await poller.history(limit)]}

@router.get('/price/evaluation')
async def evaluation(request: Request):
    st = _state(request)
    result = compare(st, getattr(st, 'ext_prices', None))
    recorder = getattr(st, 'evaluation', None)
    result['statistics'] = recorder.stats if recorder else {'n': 0, 'status': 'disabled'}
    return result

@router.get('/price/compare')
async def price_compare(request: Request):
    st = _state(request)
    result = compare(st, getattr(st, 'ext_prices', None))
    return {'t': result['t'], 'nowcaster': result['legacy'], 'external': result['reference'],
            'delta_pct': result['legacy']['error_pct'], 'delta_usd': result['legacy']['error_usd']}

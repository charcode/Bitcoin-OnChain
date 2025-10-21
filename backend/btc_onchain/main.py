from __future__ import annotations
import asyncio
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .config import SETTINGS
from .rpc import Rpc
from .core.fulcrum_client import FulcrumClient
from .core.app_state import AppState
from .api.routes import router as api_router
from .api.routes_prices import router as prices_router           # <-- NEW
from .core.external_prices import ExternalPricePoller            # <-- NEW

app = FastAPI(title="btc-onchain RNR Nowcaster", version="0.3.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

_TASKS: list[asyncio.Task] = []

@app.on_event("startup")
async def _startup():
    rpc = Rpc(SETTINGS.btc_rpc_url, SETTINGS.btc_rpc_user, SETTINGS.btc_rpc_pass)
    fulcrum = None
    if SETTINGS.fulcrum_enabled:
        fulcrum = FulcrumClient(
            host=SETTINGS.fulcrum_host,
            port=int(SETTINGS.fulcrum_port),
            use_ssl=SETTINGS.fulcrum_ssl,
            verify_ssl=SETTINGS.fulcrum_ssl_verify,
            request_timeout=SETTINGS.fulcrum_request_timeout,
        )
    app.state.app_state = AppState(rpc=rpc, fulcrum=fulcrum)

    # External prices poller
    app.state.app_state.ext_prices = None
    if SETTINGS.external_prices_enabled:
        sources = [s.strip() for s in SETTINGS.external_prices_sources_csv.split(",") if s.strip()]
        poller = ExternalPricePoller(
            db_path=SETTINGS.external_prices_db_path,
            interval_s=SETTINGS.external_prices_interval,
            sources=sources,
        )
        app.state.app_state.ext_prices = poller
        await poller.start()

    # spawn workers you already have
    _TASKS[:] = [
        asyncio.create_task(app.state.app_state.refresh_loop(), name="mempool-refresh"),
        asyncio.create_task(app.state.app_state.rnr_loop(), name="rnr-loop"),
        asyncio.create_task(app.state.app_state.stencil_loop(), name="stencil-loop"),
    ]

    app.include_router(api_router)
    app.include_router(prices_router)  # <-- NEW

@app.on_event("shutdown")
async def _shutdown():
    st: AppState = app.state.app_state
    st.stop_evt.set()
    for t in _TASKS:
        t.cancel()
    try:
        await st.rpc.aclose()
    except Exception:
        pass
    if st.fulcrum is not None:
        try:
            await st.fulcrum.aclose()
        except Exception:
            pass
    # stop poller
    if getattr(st, "ext_prices", None) is not None:
        try:
            await st.ext_prices.stop()
        except Exception:
            pass

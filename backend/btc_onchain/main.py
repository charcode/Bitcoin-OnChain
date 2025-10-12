from __future__ import annotations
import asyncio
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .config import SETTINGS
from .rpc import Rpc
from .core.fulcrum_client import FulcrumClient
from .core.app_state import AppState
from .api.routes import router as api_router

app = FastAPI(title="btc-onchain RNR Nowcaster", version="0.3.0")

# CORS for Vite dev server
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # dev
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
    # spawn workers
    _TASKS[:] = [
        asyncio.create_task(app.state.app_state.refresh_loop(), name="mempool-refresh"),
        asyncio.create_task(app.state.app_state.rnr_loop(), name="rnr-loop"),
    ]
    app.include_router(api_router)


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

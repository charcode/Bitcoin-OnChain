from __future__ import annotations
import sys, asyncio, time
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware


# Windows: avoid proactor shutdown quirks
if sys.platform.startswith("win"):
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

from .api.routes import router
from .config import settings
from .rpc import Rpc
from .workers import refresh_loop, rnr_loop

app = FastAPI(title="btc-onchain")
# allow Vite dev and localhost
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://127.0.0.1:5173", "http://localhost:5173"],
    allow_credentials=False,
    allow_methods=["GET", "OPTIONS"],
    allow_headers=["*"],
)

app.include_router(router)

# Keep refs so we can stop cleanly
_bg_tasks: list[asyncio.Task] = []
_rpc: Rpc | None = None


@app.middleware("http")
async def log_requests(request: Request, call_next):
    start = time.time()
    ts = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(start))
    try:
        response = await call_next(request)
        dur = (time.time() - start) * 1000
        print(f"[{ts}] [req] {request.method} {request.url.path} -> {response.status_code} in {dur:.1f}ms")
        return response
    except Exception as e:
        dur = (time.time() - start) * 1000
        print(f"[{ts}] [req] {request.method} {request.url.path} -> ERROR in {dur:.1f}ms: {e}")
        raise


@app.on_event("startup")
async def startup():
    global _rpc, _bg_tasks
    print(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] [startup] initializing RPC client")
    _rpc = Rpc(settings.rpc_url, settings.rpc_user, settings.rpc_pass)
    _bg_tasks = [
        asyncio.create_task(refresh_loop(_rpc)),
        asyncio.create_task(rnr_loop()),
    ]
    print(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] [startup] tasks scheduled")
    print(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] [startup] READY")


@app.on_event("shutdown")
async def shutdown():
    # cancel background tasks
    for t in _bg_tasks:
        t.cancel()
    for t in _bg_tasks:
        try:
            await t
        except asyncio.CancelledError:
            pass

    # close RPC client
    if _rpc is not None:
        try:
            await _rpc.aclose()
        except Exception as e:
            print(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] [shutdown] RPC close error: {e}")

    print(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] [shutdown] complete")


@app.get("/health")
async def health():
    return {"ok": True, "ts": time.time()}

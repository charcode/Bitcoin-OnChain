from __future__ import annotations
import os
from pydantic import BaseModel, Field


def _env_float(name: str, default: float) -> float:
    v = os.getenv(name)
    return float(v) if v is not None else default


def _env_int(name: str, default: int) -> int:
    v = os.getenv(name)
    return int(v) if v is not None else default


def _env_str(name: str, default: str) -> str:
    v = os.getenv(name)
    return v if v is not None else default


class Settings(BaseModel):
    # RPC
    btc_rpc_url: str = Field(default_factory=lambda: _env_str("BTC_RPC_URL", "http://127.0.0.1:8332"))
    btc_rpc_user: str = Field(default_factory=lambda: _env_str("BTC_RPC_USER", ""))
    btc_rpc_pass: str = Field(default_factory=lambda: _env_str("BTC_RPC_PASS", ""))

    # Mempool scanning
    lookback_sec: int = Field(default_factory=lambda: _env_int("LOOKBACK_SEC", 900))
    poll_interval: float = Field(default_factory=lambda: _env_float("POLL_INTERVAL", 5.0))
    scan_interval: float = Field(default_factory=lambda: _env_float("SCAN_INTERVAL", 10.0))
    decode_per_tick: int = Field(default_factory=lambda: _env_int("DECODE_PER_TICK", 400))
    min_samples: int = Field(default_factory=lambda: _env_int("MIN_SAMPLES", 50))

    # RNR search grid (USD)
    price_min: float = Field(default_factory=lambda: _env_float("PRICE_MIN", 30000.0))
    price_max: float = Field(default_factory=lambda: _env_float("PRICE_MAX", 120000.0))
    price_step: float = Field(default_factory=lambda: _env_float("PRICE_STEP", 50.0))

    # Kernel and smoothing
    # IMPORTANT: sigma is in USD (fixed), not proportional to price
    sigma_usd: float = Field(default_factory=lambda: _env_float("SIGMA", 50.0))
    ema_alpha: float = Field(default_factory=lambda: _env_float("EMA_ALPHA", 0.25))

    # RNR multi-grids / history
    rnr_grids: list[int] = Field(default_factory=lambda: [
        10, 25, 50, 100, 250, 500, 1000, 2000, 5000, 10000
    ])
    hist_span_mults: int = Field(default_factory=lambda: _env_int("HIST_SPAN_MULTS", 8))


SETTINGS = Settings()

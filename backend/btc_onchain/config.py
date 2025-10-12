from __future__ import annotations
import os
from pathlib import Path
from typing import List
from pydantic import BaseModel, Field

# --- load .env/local.env early so os.getenv() sees them ---
try:
    from dotenv import load_dotenv  # type: ignore
    _ROOT = Path(__file__).resolve().parent.parent  # backend/
    # Prefer local.env for secrets; then .env for defaults
    load_dotenv(dotenv_path=_ROOT / "local.env", override=False)
    load_dotenv(dotenv_path=_ROOT / ".env", override=False)
except Exception:
    # dotenv is optional; if missing we'll just rely on real env vars
    pass


def _first_env(name_options: List[str], default: str | int | float):
    for n in name_options:
        v = os.getenv(n)
        if v is not None:
            return v
    return default

def _env_float(names: str | List[str], default: float) -> float:
    if isinstance(names, str): names = [names]
    v = _first_env(names, None)
    return float(v) if v is not None else default

def _env_int(names: str | List[str], default: int) -> int:
    if isinstance(names, str): names = [names]
    v = _first_env(names, None)
    return int(v) if v is not None else default

def _env_str(names: str | List[str], default: str) -> str:
    if isinstance(names, str): names = [names]
    v = _first_env(names, None)
    return v if v is not None else default

def _env_bool(names: str | List[str], default: bool) -> bool:
    if isinstance(names, str): names = [names]
    v = _first_env(names, None)
    if v is None:
        return default
    if isinstance(v, str):
        if v.lower() in ("1", "true", "yes", "on"):
            return True
        if v.lower() in ("0", "false", "no", "off"):
            return False
    return bool(v)


def _env_int_list(name: str, default: List[int]) -> List[int]:
    raw = os.getenv(name)
    if not raw:
        return list(default)
    out: List[int] = []
    for part in raw.replace(';', ',').split(','):
        part = part.strip()
        if not part:
            continue
        try:
            out.append(int(part))
        except ValueError:
            continue
    return out if out else list(default)



class Settings(BaseModel):
    # RPC
    btc_rpc_url: str = Field(default_factory=lambda: _env_str("BTC_RPC_URL", "http://127.0.0.1:8332"))
    btc_rpc_user: str = Field(default_factory=lambda: _env_str("BTC_RPC_USER", "bitcoin"))
    btc_rpc_pass: str = Field(default_factory=lambda: _env_str("BTC_RPC_PASS", "password"))

    # Mempool scan (support both POLL_INTERVAL and SCAN_INTERVAL for compatibility)
    decode_per_tick: int = Field(default_factory=lambda: _env_int("DECODE_PER_TICK", 50))
    scan_interval: float = Field(
        default_factory=lambda: _env_float(["SCAN_INTERVAL", "POLL_INTERVAL"], 0.75)
    )
    lookback_sec: float = Field(default_factory=lambda: _env_float("LOOKBACK_SEC", 900.0))  # 15 minutes
    min_samples: int = Field(default_factory=lambda: _env_int("MIN_SAMPLES", 500))

    # RNR search space
    price_min: float = Field(default_factory=lambda: _env_float("PRICE_MIN", 20000.0))
    price_max: float = Field(default_factory=lambda: _env_float("PRICE_MAX", 120000.0))
    price_step: float = Field(default_factory=lambda: _env_float("PRICE_STEP", 50.0))

    # Kernel and smoothing
    # IMPORTANT: sigma is in USD (fixed)
    sigma_usd: float = Field(default_factory=lambda: _env_float("SIGMA", 75.0))
    ema_alpha: float = Field(default_factory=lambda: _env_float("EMA_ALPHA", 0.25))
    rnr_interval: float = Field(
        default_factory=lambda: _env_float(["RNR_INTERVAL", "SCAN_INTERVAL"], 1.0)
    )

    # Round-number grids (USD multiples)
    rnr_grids: list[int] = Field(
        default_factory=lambda: [10, 25, 50, 100, 250, 500, 1000, 2000, 5000, 10000]
    )

    # Histogram diagnostics
    hist_span_mults: int = Field(default_factory=lambda: _env_int("HIST_SPAN_MULTS", 8))
    # +/- fraction of the grid for histogram windows
    hist_sigma_frac: float = Field(default_factory=lambda: _env_float("HIST_SIGMA_FRAC", 0.20))

    # Heatmap diagnostics / visualization
    heatmap_bucket_seconds: int = Field(default_factory=lambda: _env_int("HEATMAP_BUCKET_SECONDS", 60))
    heatmap_max_buckets: int = Field(default_factory=lambda: _env_int("HEATMAP_MAX_BUCKETS", 40))
    heatmap_bin_edges_sats: List[int] = Field(
        default_factory=lambda: _env_int_list("HEATMAP_BIN_EDGES_SATS", [0, 10, 100, 1_000, 10_000, 100_000, 1_000_000, 10_000_000, 100_000_000])
    )
    distribution_bin_size_sats: int = Field(default_factory=lambda: _env_int("DIST_BIN_SIZE_SATS", 100_000))
    distribution_bin_count: int = Field(default_factory=lambda: _env_int("DIST_BIN_COUNT", 60))
    distribution_block_max: int = Field(default_factory=lambda: _env_int("DIST_BLOCK_MAX", 288))
    block_fetch_max: int = Field(default_factory=lambda: _env_int("BLOCK_FETCH_MAX", 500))
    fulcrum_enabled: bool = Field(default_factory=lambda: _env_bool("FULCRUM_ENABLED", True))
    fulcrum_host: str = Field(default_factory=lambda: _env_str("FULCRUM_HOST", "127.0.0.1"))
    fulcrum_port: int = Field(default_factory=lambda: _env_int("FULCRUM_PORT", 50002))
    fulcrum_ssl: bool = Field(default_factory=lambda: _env_bool("FULCRUM_SSL", True))
    fulcrum_ssl_verify: bool = Field(default_factory=lambda: _env_bool("FULCRUM_SSL_VERIFY", False))
    fulcrum_request_timeout: float = Field(default_factory=lambda: _env_float("FULCRUM_TIMEOUT", 30.0))

    class Config:
        arbitrary_types_allowed = True


SETTINGS = Settings()

# Post-load sanity tweaks / warnings (kept minimal; use logs in main if needed)
# If someone left old fractional sigma like 0.06, clamp to a sane USD level.
if SETTINGS.sigma_usd < 1.0:
    # Treat tiny values as misconfigured and bump to default
    SETTINGS.sigma_usd = 75.0



from __future__ import annotations
import os
from dataclasses import dataclass
from dotenv import load_dotenv

# Load defaults then local overrides
load_dotenv(".env")
load_dotenv("local.env", override=True)

@dataclass(frozen=True)
class Settings:
    rpc_url: str = os.getenv("BTC_RPC_URL", "http://127.0.0.1:8332")
    rpc_user: str = os.getenv("BTC_RPC_USER", "")
    rpc_pass: str = os.getenv("BTC_RPC_PASS", "")

    lookback_sec: int = int(os.getenv("LOOKBACK_SEC", "900"))
    poll_interval: float = float(os.getenv("POLL_INTERVAL", "5"))
    scan_interval: float = float(os.getenv("SCAN_INTERVAL", "10"))

    price_min: float = float(os.getenv("PRICE_MIN", "30000"))
    price_max: float = float(os.getenv("PRICE_MAX", "120000"))
    price_step: float = float(os.getenv("PRICE_STEP", "50"))

    sigma: float = float(os.getenv("SIGMA", "0.06"))
    ema_alpha: float = float(os.getenv("EMA_ALPHA", "0.25"))
    min_samples: int = int(os.getenv("MIN_SAMPLES", "5"))

    # mempool decode throttling
    decode_per_tick: int = int(os.getenv("DECODE_PER_TICK", "200"))

    # roundness grids
    grids: tuple[float, ...] = tuple(
        float(x) for x in os.getenv(
            "RNR_GRIDS", "10,25,50,100,250,500,1000,2000,5000,10000"
        ).split(",")
    )

    hist_span_mults: int = int(os.getenv("HIST_SPAN_MULTS", "8"))

settings = Settings()


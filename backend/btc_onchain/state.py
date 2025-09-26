# backend/btc_onchain/state.py
from __future__ import annotations
from typing import Dict, Tuple, Any, List

# key: (txid, n) -> {"value_btc": float, "first_seen": float, "weight": float}
mempool_outputs: Dict[Tuple[str, int], Dict[str, Any]] = {}

# tx first-seen timestamp
tx_first_seen: Dict[str, float] = {}

# latest EMA price estimate (float) and the full estimate object
ema_price: float | None = None
latest_estimate = None  # models.PriceEstimate | None

# cached resonance curve points [(price, score), ...] and timestamp
last_curve_points: List[Tuple[float, float]] = []
last_curve_ts: float | None = None

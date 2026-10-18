# btc_onchain/core/rnr_engine.py
from __future__ import annotations
import asyncio
import time
from collections import deque
from dataclasses import dataclass, field
from typing import Deque, Dict, List, Optional, Tuple

import numpy as np

from ..config import SETTINGS
from ..models import PriceEstimate
from ..oracle.refined import refine
from ..rnr import rnr_histogram_usd  # keep your USD hist for debug
from ..oracle.utxoracle_live import estimate_from_outputs, LiveOracleResult  # NEW

def _fmt_ts(ts: float | None = None) -> str:
    t = time.localtime(ts or time.time())
    return time.strftime("%Y-%m-%d %H:%M:%S", t)

def _is_valid_live_price(price: float | None) -> bool:
    if price is None or not np.isfinite(price):
        return False
    return SETTINGS.price_min <= float(price) <= SETTINGS.price_max

@dataclass
class RnrEngine:
    """
    Live round-number resonance engine.

    - Consumes mempool outputs (value_btc, weight, first_seen, etc).
    - Builds log10(BTC) histogram internally (UTXOracle-like).
    - Slides smooth + spike stencils to get best alignment -> USD price.
    - Smooths with EMA and exposes curve/confidence for UI.
    """
    candidate: dict = field(default_factory=dict)
    candidate_ts: float = 0.0
    last_status: str = "warming_up"
    ema_price: Optional[float] = None
    last_run_ts: float = 0.0
    last_curve: List[Tuple[float, float]] = field(default_factory=list)  # (price_usd, score)
    hist_cache: Dict[int, List[dict]] = field(default_factory=dict)      # grid -> bins list
    estimate_history: Deque[dict] = field(default_factory=lambda: deque(maxlen=600))
    # Latest computed metrics (for API/app_state)
    last_confidence: Optional[float] = None
    last_curvature: Optional[float] = None
    last_samples_used: int = 0

    def _outs_to_pairs(self, outs: List[dict]) -> List[Tuple[float, float]]:
        """
        Convert your mempool-outs dicts to (value_btc, weight) pairs expected by the oracle.
        Falls back to weight=1.0 if missing.
        """
        pairs: List[Tuple[float, float]] = []
        for o in outs:
            v = float(o.get("value_btc", 0.0))
            if v <= 0.0:
                continue
            w = float(o.get("weight", 1.0))
            if not np.isfinite(w) or w <= 0:
                w = 1.0
            pairs.append((v, w))
        return pairs

    def _update_hist_debug(self, outs: List[dict], price: float) -> None:
        """
        Keep your debug histogram endpoints working.
        Creates compact USD histograms around round-number grids at the current price.
        """
        if price <= 0.0:
            self.hist_cache.clear()
            return
        for g in SETTINGS.rnr_grids[:4]:
            half = SETTINGS.hist_sigma_frac * float(g)
            self.hist_cache[g] = rnr_histogram_usd(
                outs=outs,
                price_usd=price,
                grid=g,
                span_mults=SETTINGS.hist_span_mults,
                window_half=half,
            )

    def run_once(self, outs: List[dict]) -> Optional[PriceEstimate]:
        # Not enough samples? decay EMA slightly and skip.
        if len(outs) < SETTINGS.min_samples:
            self.last_status = "insufficient"
            self.candidate = {"status": "insufficient", "price": None, "reason": "Insufficient sample count"}
            return None

        pairs = self._outs_to_pairs(outs)
        if not pairs:
            self.last_status = "insufficient"
            return None

        # Core live UTXOracle-style estimate
        t0 = time.time()
        res: LiveOracleResult = estimate_from_outputs(pairs)
        t1 = time.time()
        if t1 - self.candidate_ts >= 10:
            seed = max(res.curve_points, key=lambda item: item[1])[0] if res.curve_points else 0.
            try:
                self.candidate = refine(pairs, seed, SETTINGS.price_min, SETTINGS.price_max)
            except Exception:
                self.candidate = {"status": "unavailable", "price": None, "reason": "Candidate computation failed"}
            self.candidate_ts = time.time()

        # Keep the resonance curve for plotting
        self.last_curve = list(res.curve_points)
        # Cache metrics for API consumption
        self.last_confidence = float(res.confidence)
        self.last_curvature = float(res.curvature)
        self.last_samples_used = int(res.samples_used)

        # EMA smoothing
        est = float(res.price) if _is_valid_live_price(res.price) else 0.0
        if est > 0:
            if self.ema_price is None:
                self.ema_price = est
            else:
                a = SETTINGS.ema_alpha
                self.ema_price = a * est + (1.0 - a) * self.ema_price
        elif self.ema_price is not None and not _is_valid_live_price(self.ema_price):
            self.ema_price = None

        # Update debug USD histograms at the *smoothed* price
        self._update_hist_debug(outs, price=float(self.ema_price or 0.0))

        self.last_status = "ok" if est > 0 else "invalid"
        if est > 0:
            self.last_run_ts = time.time()
        self.estimate_history.append(
            {
                "t": float(self.last_run_ts),
                "raw_price": float(est),
                "ema_price": float(self.ema_price or 0.0),
                "confidence": float(res.confidence),
                "curvature": float(res.curvature),
                "samples_used": int(res.samples_used),
            }
        )

        # (Optional) tiny log so you can see work + timing
        print(
            f"[{_fmt_ts()}] [rnr] samples={len(pairs):5d} "
            f"est=${est:,.0f} ema=${(self.ema_price or 0):,.0f} "
            f"conf={res.confidence:.3f} curv={res.curvature:.3f} "
            f"dt={(t1-t0)*1000:.1f}ms"
        )

        return PriceEstimate(
            t=self.last_run_ts,
            price=float(self.ema_price or 0.0),
            confidence=float(res.confidence),
            curvature=float(res.curvature),
            samples_used=int(res.samples_used),
        )

    async def run_loop(self, get_outs_callable, stop_evt: asyncio.Event) -> None:
        """
        Periodic task; call with something like:
            engine = RnrEngine()
            await engine.run_loop(lambda: list(state.mempool_outputs.values()), stop_evt)
        """
        while not stop_evt.is_set():
            try:
                outs = get_outs_callable()
                self.run_once(outs)
            except Exception as e:
                print(f"[{_fmt_ts()}] [rnr error] {e}")
            await asyncio.sleep(SETTINGS.rnr_interval)

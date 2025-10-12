# btc_onchain/core/rnr_engine.py
from __future__ import annotations
import asyncio
import time
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

import numpy as np

from ..config import SETTINGS
from ..models import PriceEstimate
from ..rnr import rnr_histogram_usd  # keep your USD hist for debug
from ..oracle.utxoracle_live import estimate_from_outputs, LiveOracleResult  # NEW

def _fmt_ts(ts: float | None = None) -> str:
    t = time.localtime(ts or time.time())
    return time.strftime("%Y-%m-%d %H:%M:%S", t)

@dataclass
class RnrEngine:
    """
    Live round-number resonance engine.

    - Consumes mempool outputs (value_btc, weight, first_seen, etc).
    - Builds log10(BTC) histogram internally (UTXOracle-like).
    - Slides smooth + spike stencils to get best alignment -> USD price.
    - Smooths with EMA and exposes curve/confidence for UI.
    """
    ema_price: Optional[float] = None
    last_run_ts: float = 0.0
    last_curve: List[Tuple[float, float]] = field(default_factory=list)  # (price_usd, score)
    hist_cache: Dict[int, List[dict]] = field(default_factory=dict)      # grid -> bins list
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
            if self.ema_price is not None:
                self.ema_price = (1.0 - SETTINGS.ema_alpha) * self.ema_price
            self.last_run_ts = time.time()
            return None

        pairs = self._outs_to_pairs(outs)
        if not pairs:
            self.last_run_ts = time.time()
            return None

        # Core live UTXOracle-style estimate
        t0 = time.time()
        res: LiveOracleResult = estimate_from_outputs(pairs)
        t1 = time.time()

        # Keep the resonance curve for plotting
        self.last_curve = list(res.curve_points)
        # Cache metrics for API consumption
        self.last_confidence = float(res.confidence)
        self.last_curvature = float(res.curvature)
        self.last_samples_used = int(res.samples_used)

        # EMA smoothing
        est = float(res.price) if np.isfinite(res.price) and res.price > 0 else 0.0
        if est > 0:
            if self.ema_price is None:
                self.ema_price = est
            else:
                a = SETTINGS.ema_alpha
                self.ema_price = a * est + (1.0 - a) * self.ema_price

        # Update debug USD histograms at the *smoothed* price
        self._update_hist_debug(outs, price=float(self.ema_price or 0.0))

        self.last_run_ts = time.time()

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

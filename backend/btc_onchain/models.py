from __future__ import annotations
from typing import List
from pydantic import BaseModel


class PriceEstimate(BaseModel):
    t: float
    price: float
    confidence: float
    curvature: float
    samples_used: int


class CurvePoint(BaseModel):
    p: float
    s: float


class CurveResp(BaseModel):
    t: float
    points: List[CurvePoint]


class CandidatesInfo(BaseModel):
    total_outputs_cached: int
    usable: int


class HistBin(BaseModel):
    price: float       # round-dollar multiple (anchor)
    count: int
    weight_sum: float


class HistogramResp(BaseModel):
    t: float
    grid: int
    span: int
    window: float      # half-width in USD
    used_price: float  # USD/BTC used to convert outputs
    bins: List[HistBin]
    total_samples: int

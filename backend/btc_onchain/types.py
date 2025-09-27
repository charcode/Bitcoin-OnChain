from __future__ import annotations
from pydantic import BaseModel
from typing import List, Dict, Optional


class CurvePoint(BaseModel):
    p: float  # price
    s: float  # z-score (normalized score)


class CurveResp(BaseModel):
    t: int
    points: List[CurvePoint]


class CandidatesInfo(BaseModel):
    total_outputs_cached: int
    usable: int


class HistogramResp(BaseModel):
    t: int
    used_price: float
    step: float
    buckets: Dict[str, int]  # bucket price (stringified) -> count
    total_samples: int

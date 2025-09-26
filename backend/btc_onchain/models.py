from __future__ import annotations
from pydantic import BaseModel
from typing import List

class PriceEstimate(BaseModel):
    t: float
    price: float
    confidence: float
    curvature: float
    samples_used: int

class CurvePoint(BaseModel):
    p: float
    s: float

class CurveResponse(BaseModel):
    t: float
    points: List[CurvePoint]

class HistogramBin(BaseModel):
    price: float
    count: int
    weight_sum: float

class HistogramResponse(BaseModel):
    t: float
    grid: float
    bins: List[HistogramBin]

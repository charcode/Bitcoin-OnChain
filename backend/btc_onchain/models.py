from __future__ import annotations
from typing import List, Literal
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


class HeatmapBucket(BaseModel):
    start: float        # inclusive bucket start (unix seconds)
    end: float          # exclusive bucket end (unix seconds)
    counts: List[int]   # counts per sat bin for the bucket


class HeatmapResp(BaseModel):
    t: float
    bucket_seconds: int
    bin_edges: List[int]
    buckets: List[HeatmapBucket]
    max_count: int
    total_samples: int
    overflow: bool

class BlockSummary(BaseModel):
    height: int
    hash: str
    time: int
    n_tx: int
    txids: List[str]


class BlocksRangeResp(BaseModel):
    start_height: int
    end_height: int
    count: int
    tip_height: int
    blocks: List[BlockSummary]

class RoundUsdStat(BaseModel):
    usd_amount: int
    bins: List[int]
    btc_amount: float
    sats: int
    normalized_weight: float
    raw_weight: float
    implied_price: float


class StencilPriceResp(BaseModel):
    start_height: int
    end_height: int
    block_count: int
    tip_height: int
    samples_used: int
    estimated_price: float
    best_slide: int
    best_slide_score: float
    neighbor_slide: int
    neighbor_score: float
    average_slide_score: float
    slides_considered: int
    usd100_btc: float
    usd100_neighbor_btc: float
    round_stats: List[RoundUsdStat]
class DistributionBin(BaseModel):
    start_sats: int
    end_sats: int
    count: int
    weight_sum: float


class DistributionResp(BaseModel):
    t: float
    source: Literal["mempool", "blocks"]
    bin_size_sats: int
    bin_count: int
    bins: List[DistributionBin]
    total_samples: int
    overflow: bool
    weighted: bool
    block_start: int | None = None
    block_end: int | None = None
    block_count: int | None = None


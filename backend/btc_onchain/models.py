from __future__ import annotations
from typing import List, Literal
from pydantic import BaseModel


class PriceEstimate(BaseModel):
    t: float
    price: float | None
    confidence: float
    curvature: float
    samples_used: int


class NodeStatus(BaseModel):
    t: float
    status: Literal["ok", "not_ready", "missing"]
    connected: bool
    message: str
    chain: str | None = None
    blocks: int | None = None
    headers: int | None = None
    initialblockdownload: bool | None = None
    mempool_size: int | None = None


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


class MempoolArrival(BaseModel):
    ts: float
    age_sec: float
    value_btc: float
    value_usd: float
    weight: float
    txid: str | None = None
    vout_n: int | None = None
    address_out: str | None = None


class RecentArrivalsResp(BaseModel):
    t: float
    current_price: float
    window_sec: int
    total_samples: int
    arrivals: List[MempoolArrival]


class EstimateHistoryPoint(BaseModel):
    t: float
    raw_price: float
    ema_price: float
    confidence: float
    curvature: float
    samples_used: int


class EstimateHistoryResp(BaseModel):
    t: float
    window_sec: int
    points: List[EstimateHistoryPoint]


class BlockTimelineSlice(BaseModel):
    height: int
    time: int
    counts: List[int]
    total_outputs: int


class BlockTimelineResp(BaseModel):
    t: float
    current_price: float
    current_block_age_sec: float
    tip_height: int
    last_block_time: int
    bin_edges_usd: List[float]
    blocks: List[BlockTimelineSlice]
    max_count: int

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

from __future__ import annotations
import time
import math
from typing import Literal
from fastapi import APIRouter, Query, Request, HTTPException

from ..models import (
    PriceEstimate,
    CurveResp,
    CurvePoint,
    CandidatesInfo,
    HistogramResp,
    HistBin,
    HeatmapResp,
    HeatmapBucket,
    BlocksRangeResp,
    BlockSummary,
    StencilPriceResp,
    DistributionResp,
    DistributionBin,
)
from ..config import SETTINGS
from ..core.stencil_price import compute_stencil_price

router = APIRouter()


def _state(request: Request):
    return request.app.state.app_state  # set in main.py


def _resolve_block_range(state, start: int, end: int | None):
    async def _resolve():
        tip_height = int(await state.rpc.call("getblockcount"))

        def resolve(value: int) -> int:
            if value >= 0:
                return value
            return tip_height + value + 1

        try:
            start_height = resolve(start)
        except Exception as exc:  # pragma: no cover - defensive
            raise HTTPException(status_code=400, detail="Invalid start parameter") from exc

        if end is None:
            end_height = tip_height if start < 0 else start_height
        else:
            end_height = resolve(end)

        if start_height < 0 or start_height > tip_height:
            raise HTTPException(status_code=400, detail="Start height out of range")
        if end_height < 0 or end_height > tip_height:
            raise HTTPException(status_code=400, detail="End height out of range")

        if start_height > end_height:
            start_h, end_h = end_height, start_height
        else:
            start_h, end_h = start_height, end_height

        count = end_h - start_h + 1
        if count <= 0:
            raise HTTPException(status_code=400, detail="Requested range is empty")
        if count > SETTINGS.block_fetch_max:
            raise HTTPException(
                status_code=400,
                detail=f"Requested range too large (>\{SETTINGS.block_fetch_max} blocks)",
            )

        return start_h, end_h, tip_height, count

    return _resolve()


@router.get("/health")
async def health():
    return {"ok": True, "t": int(time.time())}


@router.get("/price/now", response_model=PriceEstimate)
async def price_now(request: Request):
    st = _state(request)
    return st.latest_price_now()


@router.get("/rnr/curve", response_model=CurveResp)
async def rnr_curve(request: Request):
    st = _state(request)
    pts = [CurvePoint(p=float(p), s=float(s)) for p, s in st.rnr.last_curve]
    return CurveResp(t=float(time.time()), points=pts)


@router.get("/debug/candidates", response_model=CandidatesInfo)
async def debug_candidates(request: Request):
    st = _state(request)
    total = len(st.mempool.outputs)
    usable = len(st.mempool.get_recent_outputs())
    return CandidatesInfo(total_outputs_cached=total, usable=usable)


@router.get("/debug/histogram", response_model=HistogramResp)
async def debug_histogram(
    request: Request,
    grid: int = Query(100, description="Round-dollar grid size (USD multiple)"),
    span: int = Query(SETTINGS.hist_span_mults, ge=1, le=50, description="± multiples around center"),
):
    st = _state(request)
    used_price = float(st.rnr.ema_price or SETTINGS.price_min)
    half = SETTINGS.hist_sigma_frac * float(grid)
    bins_list = st.rnr.hist_cache.get(grid)

    # Compute on-demand if not yet cached
    if not bins_list:
        outs = st.mempool.get_recent_outputs()
        from ..rnr import rnr_histogram_usd
        bins_list = rnr_histogram_usd(outs, used_price, grid, span, half)

    return HistogramResp(
        t=float(time.time()),
        grid=int(grid),
        span=int(span),
        window=float(half),
        used_price=used_price,
        bins=[HistBin(**b) for b in bins_list][: 2 * span + 1],
        total_samples=len(st.mempool.get_recent_outputs()),
    )


@router.get("/debug/distribution", response_model=DistributionResp)
async def debug_distribution(
    request: Request,
    source: Literal["mempool", "blocks"] = Query("mempool", description="Data source"),
    bin_size: int = Query(SETTINGS.distribution_bin_size_sats, ge=1, description="Histogram bucket width in sats"),
    bins: int = Query(SETTINGS.distribution_bin_count, ge=1, le=500, description="Number of histogram buckets"),
    block_lookback: int = Query(144, ge=1, description="Blocks to include when source=blocks"),
    weighted: bool = Query(False, description="When true, mempool bins accumulate heuristic weights"),
    scale: Literal["linear", "log"] = Query("linear", description="Bin scale for sats distribution"),
):
    st = _state(request)
    bin_size = max(1, int(bin_size))
    bins = max(1, int(bins))

    def _make_edges(bin_size: int, count: int, scale: str) -> list[int]:
        if scale == "log":
            lo = 1
            hi = bin_size * count
            if hi <= lo:
                hi = lo + 1
            # build log-spaced edges with count+1 points
            log_lo = math.log10(max(1, lo))
            log_hi = math.log10(max(1, hi))
            step = (log_hi - log_lo) / float(count)
            edges: list[int] = []
            for i in range(count + 1):
                val = 10 ** (log_lo + i * step)
                iv = int(max(1, round(val)))
                if edges and iv <= edges[-1]:
                    iv = edges[-1] + 1
                edges.append(iv)
            edges[-1] = max(edges[-1], hi)
            return edges
        # linear
        return [i * bin_size for i in range(count + 1)]

    def _to_resp(snapshot, source_label: Literal["mempool", "blocks"]):
        edges = snapshot.edges or _make_edges(snapshot.bin_size, snapshot.bin_count, "linear")
        payload_bins = [
            DistributionBin(
                start_sats=int(edges[idx]),
                end_sats=int(edges[idx + 1]),
                count=int(count),
                weight_sum=float(snapshot.weights[idx]),
            )
            for idx, count in enumerate(snapshot.bins)
        ]
        return DistributionResp(
            t=float(snapshot.ts),
            source=source_label,
            bin_size_sats=int(snapshot.bin_size),
            bin_count=int(snapshot.bin_count),
            bins=payload_bins,
            total_samples=int(snapshot.total_samples),
            overflow=bool(snapshot.overflow),
            weighted=bool(snapshot.weighted),
            block_start=snapshot.block_start,
            block_end=snapshot.block_end,
            block_count=snapshot.block_count,
        )

    if source == "mempool":
        st.mempool.prune()
        edges = _make_edges(bin_size, bins, scale)
        snapshot = st.distributions.mempool_distribution(
            list(st.mempool.outputs),
            bin_size_sats=bin_size,
            bin_count=bins,
            weighted=bool(weighted),
            edges=edges,
        )
        return _to_resp(snapshot, "mempool")

    block_max = SETTINGS.distribution_block_max
    lookback = min(max(1, int(block_lookback)), block_max)
    try:
        edges = _make_edges(bin_size, bins, scale)
        snapshot = await st.distributions.block_distribution(
            st.rpc,
            block_lookback=lookback,
            bin_size_sats=bin_size,
            bin_count=bins,
            edges=edges,
        )
    except RuntimeError as exc:  # pragma: no cover - network path
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    return _to_resp(snapshot, "blocks")



@router.get("/debug/blocks", response_model=BlocksRangeResp)
async def debug_blocks(
    request: Request,
    start: int = Query(-10, description="Starting block height or negative offset from tip (inclusive)"),
    end: int | None = Query(
        None,
        description=(
            "Ending block height or negative offset from tip (inclusive). "
            "Defaults to the chain tip when start is negative, otherwise matches start."
        ),
    ),
):
    st = _state(request)
    start_height, end_height, tip_height, count = await _resolve_block_range(st, start, end)

    blocks: list[BlockSummary] = []
    for height in range(start_height, end_height + 1):
        block_hash = await st.rpc.call("getblockhash", [height])
        block = await st.rpc.call("getblock", [block_hash, 1])
        txids = block.get("tx", []) if isinstance(block, dict) else []
        blocks.append(
            BlockSummary(
                height=height,
                hash=str(block_hash),
                time=int(block.get("time", 0)) if isinstance(block, dict) else 0,
                n_tx=int(block.get("nTx", len(txids))) if isinstance(block, dict) else len(txids),
                txids=[str(tx) for tx in txids],
            )
        )

    return BlocksRangeResp(
        start_height=start_height,
        end_height=end_height,
        count=count,
        tip_height=tip_height,
        blocks=blocks,
    )


@router.get("/debug/stencil_price", response_model=StencilPriceResp)
async def debug_stencil_price(
    request: Request,
    start: int = Query(-144, description="Starting block height or negative offset from tip (inclusive)"),
    end: int | None = Query(
        None,
        description=(
            "Ending block height or negative offset from tip (inclusive). "
            "Defaults to the chain tip when start is negative, otherwise matches start."
        ),
    ),
):
    st = _state(request)
    start_height, end_height, tip_height, count = await _resolve_block_range(st, start, end)

    # Serve cached result for the common case "last N blocks"
    if (
        st.stencil_cache is not None
        and st.stencil_cache_start == start_height
        and st.stencil_cache_end == end_height
    ):
        cached = st.stencil_cache
        return StencilPriceResp(
            start_height=start_height,
            end_height=end_height,
            block_count=count,
            tip_height=tip_height,
            **cached,
        )

    try:
        result = await compute_stencil_price(st.rpc, st.fulcrum, start_height, end_height)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    resp = StencilPriceResp(
        start_height=start_height,
        end_height=end_height,
        block_count=count,
        tip_height=tip_height,
        **result,
    )
    # Update cache for "last N blocks"
    try:
        st.stencil_cache = {
            "start_height": start_height,
            "end_height": end_height,
            "block_count": count,
            **result,
        }
        st.stencil_cache_start = start_height
        st.stencil_cache_end = end_height
        st.stencil_estimated_price = float(result.get("estimated_price", 0.0))
        st.stencil_cache_ts = time.time()
    except Exception:
        pass

    return resp


@router.get("/debug/heatmap", response_model=HeatmapResp)
async def debug_heatmap(
    request: Request,
    bucket: int = Query(
        SETTINGS.heatmap_bucket_seconds,
        ge=5,
        le=900,
        description="Seconds per heatmap column",
    ),
    buckets: int = Query(
        SETTINGS.heatmap_max_buckets,
        ge=1,
        le=240,
        description="How many recent time buckets to include",
    ),
):
    st = _state(request)
    payload = st.mempool.build_heatmap(
        bucket_seconds=bucket,
        max_buckets=buckets,
        bin_edges=SETTINGS.heatmap_bin_edges_sats,
    )

    return HeatmapResp(
        t=float(payload["t"]),
        bucket_seconds=int(payload["bucket_seconds"]),
        bin_edges=[int(x) for x in payload["bin_edges"]],
        buckets=[HeatmapBucket(**b) for b in payload["buckets"]],
        max_count=int(payload["max_count"]),
        total_samples=int(payload["total_samples"]),
        overflow=bool(payload["overflow"]),
    )





import { useCallback, useEffect, useMemo, useRef, useState } from "react";

import { getBlockTimeline, getEstimateHistory, getRecentArrivals } from "../lib/api";
import type {
  BlockTimelineResp,
  EstimateHistoryResp,
  MempoolArrival,
  RecentArrivalsResp,
} from "../lib/types";

type Props = {
  bucketSeconds: number;
  columnCount: number;
  refreshToken: number;
};

const USD = new Intl.NumberFormat(undefined, {
  style: "currency",
  currency: "USD",
  maximumFractionDigits: 0,
});

const GUIDE_VALUES = [10, 25, 50, 100, 250, 500, 1_000, 2_000, 5_000, 10_000];
const SVG_HEIGHT = 360;
const PLOT_TOP = 26;
const PLOT_BOTTOM = 40;
const CENTER_X = 46;
const LEFT_X0 = 6;
const RIGHT_X1 = 98;
const HISTORY_HEIGHT = 118;

function clamp(value: number, min: number, max: number) {
  return Math.min(Math.max(value, min), max);
}

function fmtCompact(value: number) {
  if (value >= 1_000_000) return (value / 1_000_000).toFixed(1) + "M";
  if (value >= 1_000) return (value / 1_000).toFixed(1) + "k";
  return value.toLocaleString();
}

function fmtSince(seconds: number) {
  if (seconds >= 3600) return (seconds / 3600).toFixed(1) + "h";
  if (seconds >= 60) return Math.round(seconds / 60) + "m";
  return Math.round(seconds) + "s";
}

function buildHistoryPath(points: EstimateHistoryResp["points"], width: number, height: number) {
  if (points.length < 2) return "";
  const prices = points.map((point) => point.ema_price).filter((value) => Number.isFinite(value) && value > 0);
  if (prices.length < 2) return "";

  const minPrice = Math.min(...prices);
  const maxPrice = Math.max(...prices);
  const spread = Math.max(1, maxPrice - minPrice);
  const startTs = points[0].t;
  const endTs = points[points.length - 1].t;
  const timeSpan = Math.max(1, endTs - startTs);

  return points
    .map((point, index) => {
      const x = ((point.t - startTs) / timeSpan) * width;
      const y = height - ((point.ema_price - minPrice) / spread) * height;
      return `${index === 0 ? "M" : "L"} ${x.toFixed(2)} ${y.toFixed(2)}`;
    })
    .join(" ");
}

function colorForHeat(value: number, maxValue: number) {
  if (value <= 0 || maxValue <= 0) return "rgba(30,41,59,0.16)";
  const ratio = Math.min(1, value / maxValue);
  const alpha = 0.25 + Math.pow(ratio, 0.68) * 0.72;
  return `rgba(232, 121, 249, ${alpha.toFixed(3)})`;
}

function resolveYBounds(arrivals: MempoolArrival[], currentPrice: number, timeline: BlockTimelineResp | null) {
  if (timeline && timeline.bin_edges_usd.length >= 2) {
    return {
      min: timeline.bin_edges_usd[0],
      max: timeline.bin_edges_usd[timeline.bin_edges_usd.length - 1],
    };
  }

  const values = arrivals
    .map((arrival) => arrival.value_usd)
    .filter((value) => Number.isFinite(value) && value > 0);

  if (currentPrice > 0) {
    values.push(currentPrice * 0.35, currentPrice, currentPrice * 1.75);
  }

  if (values.length === 0) return { min: 10, max: 100000 };
  const min = Math.max(1, Math.min(...values) * 0.75);
  const max = Math.max(min * 1.2, Math.max(...values) * 1.15);
  return { min, max };
}

export default function TransactionsHeatmap({ bucketSeconds, columnCount, refreshToken }: Props) {
  const [arrivalsResp, setArrivalsResp] = useState<RecentArrivalsResp | null>(null);
  const [historyResp, setHistoryResp] = useState<EstimateHistoryResp | null>(null);
  const [timelineResp, setTimelineResp] = useState<BlockTimelineResp | null>(null);
  const [loading, setLoading] = useState(false);
  const [err, setErr] = useState<string | null>(null);
  const [nowTs, setNowTs] = useState<number>(Date.now() / 1000);
  const timelineParamsRef = useRef<{ price: number; min: number; max: number }>({
    price: 0,
    min: 10,
    max: 100000,
  });

  const arrivalWindowSec = Math.max(60, bucketSeconds * columnCount);
  const currentPrice =
    arrivalsResp?.current_price ??
    timelineResp?.current_price ??
    historyResp?.points.at(-1)?.ema_price ??
    0;

  const yBounds = useMemo(
    () => resolveYBounds(arrivalsResp?.arrivals ?? [], currentPrice, timelineResp),
    [arrivalsResp, currentPrice, timelineResp]
  );

  const fetchLive = useCallback(async () => {
    try {
      const [arrivals, history] = await Promise.all([
        getRecentArrivals({ window_sec: arrivalWindowSec, limit: 2200 }),
        getEstimateHistory({ window_sec: Math.max(180, arrivalWindowSec), limit: 360 }),
      ]);
      setArrivalsResp(arrivals);
      setHistoryResp(history);
      setErr(null);
    } catch (error: any) {
      setErr(error?.message ?? String(error));
      setArrivalsResp(null);
      setHistoryResp(null);
    } finally {
      setLoading(false);
    }
  }, [arrivalWindowSec]);

  useEffect(() => {
    timelineParamsRef.current = {
      price: currentPrice,
      min: yBounds.min,
      max: yBounds.max,
    };
  }, [currentPrice, yBounds.max, yBounds.min]);

  const fetchTimeline = useCallback(async () => {
    try {
      const params = timelineParamsRef.current;
      const timeline = await getBlockTimeline({
        block_count: 6,
        bin_count: 26,
        min_usd: params.min,
        max_usd: params.max,
        price_usd: params.price && params.price > 0 ? params.price : undefined,
      });
      setTimelineResp(timeline);
      setErr(null);
    } catch (error: any) {
      setErr(error?.message ?? String(error));
      setTimelineResp(null);
    }
  }, []);

  useEffect(() => {
    setLoading(true);
    fetchLive();
  }, [fetchLive, refreshToken]);

  useEffect(() => {
    const id = window.setInterval(fetchLive, 1000);
    return () => window.clearInterval(id);
  }, [fetchLive]);

  useEffect(() => {
    fetchTimeline();
    const id = window.setInterval(fetchTimeline, 15000);
    return () => window.clearInterval(id);
  }, [fetchTimeline, refreshToken]);

  useEffect(() => {
    const id = window.setInterval(() => setNowTs(Date.now() / 1000), 120);
    return () => window.clearInterval(id);
  }, []);

  const blockAgeSec = Math.max(30, timelineResp?.current_block_age_sec ?? arrivalWindowSec);
  const visibleArrivals = useMemo(
    () =>
      (arrivalsResp?.arrivals ?? []).filter((arrival) => {
        const age = Math.max(0, nowTs - arrival.ts);
        return age <= blockAgeSec && arrival.value_usd > 0;
      }),
    [arrivalsResp, nowTs, blockAgeSec]
  );

  const logMin = Math.log10(Math.max(0.01, yBounds.min));
  const logSpan = Math.max(0.0001, Math.log10(yBounds.max) - logMin);
  const plotHeight = SVG_HEIGHT - PLOT_TOP - PLOT_BOTTOM;

  const guideLines = useMemo(
    () =>
      GUIDE_VALUES.filter((value) => value >= yBounds.min && value <= yBounds.max).map((value) => {
        const y = PLOT_TOP + (1 - (Math.log10(value) - logMin) / logSpan) * plotHeight;
        return { value, y };
      }),
    [logMin, logSpan, plotHeight, yBounds.max, yBounds.min]
  );

  const currentPriceY = useMemo(() => {
    if (!(currentPrice > 0)) return null;
    return PLOT_TOP + (1 - (Math.log10(currentPrice) - logMin) / logSpan) * plotHeight;
  }, [currentPrice, logMin, logSpan, plotHeight]);

  const blockColumns = useMemo(() => {
    const blocks = timelineResp?.blocks ?? [];
    if (!blocks.length || !timelineResp) return [];
    const width = CENTER_X - LEFT_X0 - 1.5;
    const colWidth = width / blocks.length;

    return blocks.map((block, idx) => {
      const x0 = LEFT_X0 + idx * colWidth;
      const x1 = x0 + colWidth - 0.8;
      const cells = block.counts.map((count, binIdx) => {
        const start = timelineResp.bin_edges_usd[binIdx];
        const end = timelineResp.bin_edges_usd[binIdx + 1];
        const y0 = PLOT_TOP + (1 - (Math.log10(end) - logMin) / logSpan) * plotHeight;
        const y1 = PLOT_TOP + (1 - (Math.log10(start) - logMin) / logSpan) * plotHeight;
        return {
          count,
          y: y0,
          height: Math.max(0.5, y1 - y0),
          fill: colorForHeat(count, timelineResp.max_count),
        };
      });
      return {
        ...block,
        x0,
        x1,
        center: (x0 + x1) / 2,
        cells,
      };
    });
  }, [timelineResp, logMin, logSpan, plotHeight]);

  const arrivalMarks = useMemo(() => {
    const rightWidth = RIGHT_X1 - CENTER_X - 1.5;
    return visibleArrivals.map((arrival, index) => {
      const age = Math.max(0, nowTs - arrival.ts);
      const normalizedAge = clamp(age / Math.max(1, blockAgeSec), 0, 1);
      // Use a concave easing so recent arrivals occupy much more of the right-hand width.
      const eased = Math.pow(normalizedAge, 0.58);
      const x = RIGHT_X1 - eased * rightWidth;
      const y = PLOT_TOP + (1 - (Math.log10(arrival.value_usd) - logMin) / logSpan) * plotHeight;
      const freshness = 1 - normalizedAge;
      const radius = 1.7 + Math.min(5.8, arrival.weight * 5.5);
      const opacity = 0.18 + freshness * 0.82;
      const hue = clamp(210 + arrival.weight * 115, 210, 330);
      return {
        key: `${arrival.ts}-${arrival.txid ?? "tx"}-${arrival.vout_n ?? index}`,
        x,
        y,
        radius,
        opacity,
        hue,
        arrival,
      };
    });
  }, [visibleArrivals, nowTs, blockAgeSec, logMin, logSpan, plotHeight]);

  const historyPath = useMemo(() => buildHistoryPath(historyResp?.points ?? [], 100, 100), [historyResp]);
  const latestPoint = historyResp?.points.at(-1) ?? null;
  const oldestPoint = historyResp?.points[0] ?? null;
  const priceDelta =
    latestPoint && oldestPoint && oldestPoint.ema_price > 0
      ? ((latestPoint.ema_price - oldestPoint.ema_price) / oldestPoint.ema_price) * 100
      : null;

  return (
    <div className="space-y-5">
      <div className="flex flex-wrap items-center justify-between gap-3 text-sm text-slate-400">
        <div>
          {loading && <span>Loading timeline...</span>}
          {!loading && (
            <span>
              {timelineResp?.blocks.length ?? 0} blocks left | {fmtCompact(visibleArrivals.length)} mempool arrivals right | block age {fmtSince(blockAgeSec)}
            </span>
          )}
        </div>
        <div className="text-xs uppercase tracking-[0.3em] text-slate-400">
          {currentPrice > 0 ? `EMA ${USD.format(currentPrice)}` : "EMA waiting"}
        </div>
      </div>

      {err && <div className="rounded-xl border border-rose-500/40 bg-rose-500/10 p-3 text-sm text-rose-200">{err}</div>}

      <div className="rounded-[24px] border border-slate-700/50 bg-slate-950/72 p-4 shadow-[0_18px_50px_rgba(2,6,23,0.45)]">
        <div className="mb-4 flex flex-wrap items-center justify-between gap-3">
          <div>
            <div className="text-xs uppercase tracking-[0.35em] text-slate-400">Block-to-now timeline</div>
            <div className="mt-1 text-sm text-slate-300/80">
              Left: recent confirmed blocks in fixed slots. Center: last block boundary. Right: mempool arrivals moving toward the boundary on a compressed time scale.
            </div>
          </div>
          <div className="text-right text-xs text-slate-300/80">
            <div>{timelineResp ? `tip ${timelineResp.tip_height.toLocaleString()}` : "tip --"}</div>
            <div>{latestPoint ? `confidence ${(latestPoint.confidence * 100).toFixed(0)}%` : "confidence --"}</div>
          </div>
        </div>

        <div className="relative overflow-hidden rounded-[22px] border border-slate-800/80 bg-[radial-gradient(circle_at_top,rgba(14,165,233,0.12),transparent_40%),linear-gradient(180deg,rgba(10,18,39,0.98),rgba(2,6,23,0.99))]">
          <svg viewBox={`0 0 100 ${SVG_HEIGHT}`} className="block h-[360px] w-full">
            <rect x={LEFT_X0} y={PLOT_TOP - 6} width={CENTER_X - LEFT_X0 - 0.8} height={plotHeight + 12} fill="rgba(56,189,248,0.045)" />
            <rect x={CENTER_X + 0.4} y={PLOT_TOP - 6} width={RIGHT_X1 - CENTER_X - 0.4} height={plotHeight + 12} fill="rgba(244,114,182,0.035)" />

            {guideLines.map((guide) => (
              <g key={guide.value}>
                <line x1={LEFT_X0} x2={RIGHT_X1} y1={guide.y} y2={guide.y} stroke="rgba(148,163,184,0.12)" strokeDasharray="1.5 1.8" />
                <text x="1.5" y={guide.y - 1.2} fill="rgba(203,213,225,0.7)" fontSize="3">
                  {USD.format(guide.value)}
                </text>
              </g>
            ))}

            {blockColumns.map((block) => (
              <g key={block.height}>
                <rect
                  x={block.x0}
                  y={PLOT_TOP}
                  width={Math.max(0.8, block.x1 - block.x0)}
                  height={plotHeight}
                  fill="rgba(15,23,42,0.12)"
                  stroke="rgba(148,163,184,0.14)"
                  strokeWidth="0.18"
                />
                {block.cells.map((cell, idx) => (
                  <rect
                    key={`${block.height}-${idx}`}
                    x={block.x0}
                    y={cell.y}
                    width={Math.max(0.8, block.x1 - block.x0)}
                    height={cell.height}
                    fill={cell.fill}
                  />
                ))}
                <text x={block.center} y={SVG_HEIGHT - 12} textAnchor="middle" fill="rgba(148,163,184,0.82)" fontSize="2.7">
                  {block.height}
                </text>
              </g>
            ))}

            <line x1={CENTER_X} x2={CENTER_X} y1={PLOT_TOP - 10} y2={SVG_HEIGHT - 8} stroke="rgba(125,211,252,0.9)" strokeWidth="0.55" />
            <text x={CENTER_X} y={PLOT_TOP - 13} textAnchor="middle" fill="rgba(125,211,252,0.95)" fontSize="3">
              last block
            </text>
            <text x={RIGHT_X1} y={PLOT_TOP - 13} textAnchor="end" fill="rgba(244,114,182,0.95)" fontSize="3">
              now
            </text>

            {currentPriceY !== null && (
              <g>
                <line x1={LEFT_X0} x2={RIGHT_X1} y1={currentPriceY} y2={currentPriceY} stroke="rgba(56,189,248,0.8)" strokeWidth="0.45" />
                <text x={CENTER_X + 1.5} y={currentPriceY - 1.3} fill="rgba(125,211,252,0.95)" fontSize="3">
                  live estimate
                </text>
              </g>
            )}

            {arrivalMarks.map((mark) => (
              <g key={mark.key}>
                <circle
                  cx={mark.x}
                  cy={mark.y}
                  r={mark.radius * 1.7}
                  fill={`hsla(${mark.hue}, 90%, 65%, ${mark.opacity * 0.12})`}
                />
                <circle
                  cx={mark.x}
                  cy={mark.y}
                  r={mark.radius}
                  fill={`hsla(${mark.hue}, 95%, 68%, ${mark.opacity})`}
                  stroke={`hsla(${mark.hue}, 100%, 90%, ${Math.min(1, mark.opacity + 0.1)})`}
                  strokeWidth="0.15"
                />
              </g>
            ))}

            <text x={LEFT_X0} y={SVG_HEIGHT - 28} fill="rgba(148,163,184,0.78)" fontSize="2.8">
              recent blocks
            </text>
            <text x={RIGHT_X1} y={SVG_HEIGHT - 28} textAnchor="end" fill="rgba(244,114,182,0.78)" fontSize="2.8">
              this block mempool
            </text>
          </svg>
        </div>

        <div className="mt-5 grid gap-3 sm:grid-cols-4 text-xs text-slate-300/80">
          <div className="rounded-2xl border border-slate-800/70 bg-slate-900/65 px-4 py-3">
            <div className="text-slate-400">Blocks shown</div>
            <div className="mt-1 text-lg font-semibold text-indigo-200">{timelineResp?.blocks.length ?? 0}</div>
          </div>
          <div className="rounded-2xl border border-slate-800/70 bg-slate-900/65 px-4 py-3">
            <div className="text-slate-400">Mempool arrivals</div>
            <div className="mt-1 text-lg font-semibold text-sky-200">{fmtCompact(visibleArrivals.length)}</div>
          </div>
          <div className="rounded-2xl border border-slate-800/70 bg-slate-900/65 px-4 py-3">
            <div className="text-slate-400">Current block age</div>
            <div className="mt-1 text-lg font-semibold text-pink-200">{fmtSince(blockAgeSec)}</div>
          </div>
          <div className="rounded-2xl border border-slate-800/70 bg-slate-900/65 px-4 py-3">
            <div className="text-slate-400">Window delta</div>
            <div className="mt-1 text-lg font-semibold text-amber-200">
              {priceDelta !== null ? `${priceDelta >= 0 ? "+" : ""}${priceDelta.toFixed(2)}%` : "--"}
            </div>
          </div>
        </div>
      </div>

      <div className="rounded-[24px] border border-slate-700/50 bg-slate-950/70 p-4 shadow-[0_18px_50px_rgba(2,6,23,0.35)]">
        <div className="mb-4 flex flex-wrap items-center justify-between gap-3">
          <div>
            <div className="text-xs uppercase tracking-[0.35em] text-slate-400">Estimate reaction</div>
            <div className="mt-1 text-sm text-slate-300/80">
              Rolling view of the live estimate responding while new arrivals flow from the right-hand side.
            </div>
          </div>
          <div className="text-xs text-slate-300/80">
            {latestPoint ? `samples ${fmtCompact(latestPoint.samples_used)}` : "samples --"}
          </div>
        </div>

        <div className="relative overflow-hidden rounded-[22px] border border-slate-800/80 bg-slate-950/80 px-3 py-4">
          <svg viewBox={`0 0 100 ${HISTORY_HEIGHT}`} className="block h-[118px] w-full">
            <line x1="0" x2="100" y1={HISTORY_HEIGHT - 6} y2={HISTORY_HEIGHT - 6} stroke="rgba(148,163,184,0.18)" />
            {[20, 40, 60, 80].map((tick) => (
              <line key={tick} x1={tick} x2={tick} y1="8" y2={HISTORY_HEIGHT - 6} stroke="rgba(148,163,184,0.06)" strokeDasharray="1 1.5" />
            ))}
            {historyPath ? (
              <path d={historyPath} fill="none" stroke="rgba(56,189,248,0.95)" strokeWidth="2.2" strokeLinecap="round" />
            ) : (
              <text x="50" y="60" textAnchor="middle" fill="rgba(148,163,184,0.8)" fontSize="5">
                waiting for estimate history
              </text>
            )}
          </svg>
        </div>
      </div>

      {!loading && !err && !timelineResp && visibleArrivals.length === 0 && (
        <div className="rounded-xl border border-slate-700/60 bg-slate-900/60 p-6 text-sm text-slate-400">
          The timeline will populate once the backend has both recent block context and fresh mempool arrivals.
        </div>
      )}
    </div>
  );
}

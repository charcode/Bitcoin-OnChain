
import { useEffect, useMemo, useState } from "react";
import {
  ResponsiveContainer,
  ComposedChart,
  CartesianGrid,
  Bar,
  XAxis,
  YAxis,
  Tooltip,
  ReferenceLine,
  Brush,
} from "recharts";

import { getDistribution } from "../lib/api";
import type { DistributionResp } from "../lib/types";

type ScaleOption = "linear" | "sqrt" | "log";

type Props = {
  source: "mempool" | "blocks";
  binSize: number;
  binCount: number;
  blockLookback: number;
  weighted: boolean;
  scale: ScaleOption;
  showRoundLines: boolean;
  roundUsdAnchors: number[];
  priceUsd: number | null;
  refreshToken: number;
};

const SATS_PER_BTC = 100_000_000;

const formatSats = (value: number, withUnit = true) => {
  if (value >= 100_000_000) return (value / 100_000_000).toFixed(2) + (withUnit ? " BTC" : "");
  if (value >= 1_000_000) return (value / 1_000_000).toFixed(1) + (withUnit ? "M sats" : "M");
  if (value >= 1_000) return (value / 1_000).toFixed(1) + (withUnit ? "k sats" : "k");
  return value.toLocaleString() + (withUnit ? " sats" : "");
};

const formatCount = (value: number) => {
  if (value >= 1_000_000) return (value / 1_000_000).toFixed(1) + "M";
  if (value >= 1_000) return (value / 1_000).toFixed(1) + "k";
  return value.toLocaleString();
};

type ChartPoint = {
  midpoint: number;
  start: number;
  end: number;
  count: number;
  weight: number;
  display: number;
  overflow: boolean;
};

type RoundAnchor = {
  usd: number;
  sats: number;
};

type CustomTooltipProps = {
  tooltip: {
    active?: boolean;
    payload?: Array<{ payload?: ChartPoint } | undefined> | undefined;
  };
  anchors: RoundAnchor[];
  priceUsd: number | null;
};

const transformValue = (value: number, scale: ScaleOption) => {
  if (scale === "log") return Math.log10(value + 1);
  if (scale === "sqrt") return Math.sqrt(value);
  return value;
};

const invertValue = (value: number, scale: ScaleOption) => {
  if (scale === "log") return Math.pow(10, value) - 1;
  if (scale === "sqrt") return value * value;
  return value;
};

const CustomTooltip = ({ tooltip, anchors, priceUsd }: CustomTooltipProps) => {
  const { active, payload } = tooltip;
  if (!active || !payload || !payload.length) return null;
  const chartPoint = payload[0]?.payload as ChartPoint | undefined;
  if (!chartPoint) return null;

  const nearest = (() => {
    if (!priceUsd || !anchors.length) return null;
    const midpoint = chartPoint.midpoint;
    let best: RoundAnchor | null = null;
    let bestDiff = Number.POSITIVE_INFINITY;
    for (const anchor of anchors) {
      const diff = Math.abs(anchor.sats - midpoint);
      if (diff < bestDiff) {
        bestDiff = diff;
        best = anchor;
      }
    }
    return best
      ? {
          ...best,
          diffSats: best.sats - midpoint,
          diffUsd: ((best.sats - midpoint) * priceUsd) / SATS_PER_BTC,
        }
      : null;
  })();

  return (
    <div className="min-w-[240px] space-y-2 rounded-xl border border-slate-700 bg-slate-900/90 px-4 py-3 text-xs text-slate-100 shadow-lg">
      <div className="font-semibold text-slate-100">
        {formatSats(chartPoint.start)} - {formatSats(chartPoint.end)}
      </div>
      <div className="flex items-center justify-between text-slate-300">
        <span>Count</span>
        <span className="font-semibold text-sky-200">{chartPoint.count.toLocaleString()}</span>
      </div>
      <div className="flex items-center justify-between text-slate-300">
        <span>Bin midpoint</span>
        <span>{formatSats(chartPoint.midpoint)}</span>
      </div>
      {nearest && (
        <div className="space-y-1 rounded-lg border border-sky-400/40 bg-sky-500/10 px-3 py-2 text-[11px] text-sky-100">
          <div>Nearest round USD: ${nearest.usd.toLocaleString()}</div>
          <div>Offset {formatSats(Math.abs(nearest.diffSats))} ({nearest.diffUsd.toFixed(2)} USD)</div>
        </div>
      )}
      {chartPoint.overflow && <div className="text-[11px] text-amber-300">Overflow bin (captures larger outputs).</div>}
    </div>
  );
};

export default function SatsDistributionPanel({
  source,
  binSize,
  binCount,
  blockLookback,
  weighted,
  scale,
  showRoundLines,
  roundUsdAnchors,
  priceUsd,
  refreshToken,
}: Props) {
  const [data, setData] = useState<DistributionResp | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [brushRange, setBrushRange] = useState<[number, number] | null>(null);

  useEffect(() => {
    let alive = true;

    const fetchData = async () => {
      setLoading(true);
      setError(null);
      try {
        const payload = await getDistribution({
          source,
          bin_size: binSize,
          bins: binCount,
          block_lookback: source === "blocks" ? blockLookback : undefined,
          weighted: source === "mempool" ? weighted : undefined,
        });
        if (!alive) return;
        setData(payload);
        setBrushRange(null);
      } catch (err) {
        if (!alive) return;
        setData(null);
        setError(err instanceof Error ? err.message : String(err));
      } finally {
        if (alive) setLoading(false);
      }
    };

    fetchData();
    return () => {
      alive = false;
    };
  }, [source, binSize, binCount, blockLookback, weighted, refreshToken]);

  const baseDataset = useMemo<ChartPoint[]>(() => {
    if (!data) return [];
    return data.bins.map((bin, index) => {
      const midpoint = bin.start_sats + (bin.end_sats - bin.start_sats) / 2;
      return {
        midpoint,
        start: bin.start_sats,
        end: bin.end_sats,
        count: bin.count,
        weight: bin.weight_sum,
        display: transformValue(bin.count, scale),
        overflow: data.overflow && index === data.bins.length - 1,
      };
    });
  }, [data, scale]);

  const xDomain = useMemo<[number, number] | ["dataMin", "dataMax"]>(() => {
    if (!baseDataset.length) return ["dataMin", "dataMax"];
    if (!brushRange) return ["dataMin", "dataMax"];
    const [startIndex, endIndex] = brushRange;
    const startValue = baseDataset[startIndex]?.midpoint ?? baseDataset[0].midpoint;
    const endValue = baseDataset[endIndex]?.midpoint ?? baseDataset[baseDataset.length - 1].midpoint;
    return [startValue, endValue];
  }, [baseDataset, brushRange]);

  const visibleDataset = useMemo(() => {
    if (!baseDataset.length) return baseDataset;
    if (!brushRange) return baseDataset;
    const [start, end] = brushRange;
    return baseDataset.slice(start, end + 1);
  }, [baseDataset, brushRange]);

  const domainY = useMemo<[number, number]>(() => {
    if (!visibleDataset.length) return [0, 1];
    const maxDisplay = Math.max(...visibleDataset.map((point) => point.display));
    return [0, maxDisplay === 0 ? 1 : maxDisplay * 1.08];
  }, [visibleDataset]);

  const anchors = useMemo<RoundAnchor[]>(() => {
    if (!priceUsd || priceUsd <= 0) return [];
    return roundUsdAnchors
      .map((usd) => ({ usd, sats: (usd * SATS_PER_BTC) / priceUsd }))
      .filter((entry) => entry.sats > 0)
      .sort((a, b) => a.sats - b.sats);
  }, [roundUsdAnchors, priceUsd]);

  return (
    <div className="space-y-5">
      <div className="text-sm text-slate-400">
        {loading && <span>Loading distribution...</span>}
        {!loading && data && (
          <span>
            Samples {data.total_samples.toLocaleString()} | bin width {formatSats(binSize)} | bins {binCount}
            {data.source === "blocks" && data.block_start !== null && data.block_end !== null
              ? ` | blocks ${data.block_start.toLocaleString()}-${data.block_end.toLocaleString()}`
              : ""}
            {data.weighted ? " | weighted" : ""}
          </span>
        )}
        {!loading && !data && !error && <span>No distribution data yet.</span>}
      </div>

      {error && (
        <div className="rounded-xl border border-rose-500/40 bg-rose-500/10 p-3 text-sm text-rose-200">{error}</div>
      )}

      {data && (
        <div className="rounded-[24px] border border-slate-700/40 bg-slate-900/50 p-4">
          <ResponsiveContainer width="100%" height={360}>
            <ComposedChart data={baseDataset} margin={{ top: 16, right: 24, bottom: 24, left: 64 }}>
              <CartesianGrid strokeDasharray="2 4" stroke="#1f2937" />
              <XAxis
                dataKey="midpoint"
                type="number"
                domain={xDomain}
                tickFormatter={(value) => formatSats(value, false)}
                tick={{ fill: "#cbd5f5", fontSize: 11 }}
              />
              <YAxis
                type="number"
                domain={domainY}
                tickFormatter={(value) => formatCount(Math.round(invertValue(value, scale)))}
                tick={{ fill: "#cbd5f5", fontSize: 11 }}
              />
              <Tooltip
                cursor={{ fill: "rgba(56, 189, 248, 0.1)" }}
                content={(props) => <CustomTooltip tooltip={props} anchors={anchors} priceUsd={priceUsd} />}
              />
              <Bar dataKey="display" fill={source === "mempool" ? "#38bdf8" : "#facc15"} radius={[4, 4, 0, 0]} />
              {showRoundLines &&
                anchors.map((anchor) => (
                  <ReferenceLine
                    key={anchor.usd}
                    x={anchor.sats}
                    stroke="#f97316"
                    strokeDasharray="4 4"
                    label={{ position: "top", value: `$${anchor.usd.toLocaleString()}`, fill: "#f97316", fontSize: 10 }}
                  />
                ))}
              <Brush
                dataKey="midpoint"
                height={24}
                stroke="#38bdf8"
                travellerWidth={12}
                startIndex={brushRange ? brushRange[0] : undefined}
                endIndex={brushRange ? brushRange[1] : undefined}
                onChange={(range) => {
                  if (range && typeof range === "object") {
                    const { startIndex, endIndex } = range as { startIndex?: number; endIndex?: number };
                    if (
                      typeof startIndex === "number" &&
                      typeof endIndex === "number" &&
                      startIndex <= endIndex
                    ) {
                      setBrushRange([startIndex, endIndex]);
                      return;
                    }
                  }
                  setBrushRange(null);
                }}
              />
            </ComposedChart>
          </ResponsiveContainer>
        </div>
      )}

      {data && data.overflow && (
        <div className="rounded-xl border border-amber-500/40 bg-amber-500/10 px-3 py-2 text-xs text-amber-200">
          Overflow: outputs above the final bin are aggregated into the last bucket.
        </div>
      )}

      {data && baseDataset.length > 0 && (
        <div className="space-y-2">
          <div className="text-xs uppercase tracking-[0.3em] text-slate-400">Top buckets</div>
          <div className="grid gap-2 text-xs text-slate-200 sm:grid-cols-2 lg:grid-cols-3">
            {baseDataset
              .map((point, index) => ({ point, index }))
              .sort((a, b) => b.point.count - a.point.count)
              .slice(0, 6)
              .map(({ point, index }) => (
                <div
                  key={index}
                  className="rounded-xl border border-slate-700/50 bg-slate-900/60 p-3 shadow-[0_6px_16px_rgba(15,23,42,0.35)]"
                >
                  <div className="flex items-center justify-between text-slate-300">
                    <span>
                      {formatSats(point.start)} - {formatSats(point.end)}
                    </span>
                    <span className="font-semibold text-sky-200">{point.count.toLocaleString()}</span>
                  </div>
                  <div className="mt-1 text-[11px] text-slate-400">
                    {point.count.toLocaleString()} samples - midpoint {formatSats(point.midpoint)}
                  </div>
                  {data.weighted && (
                    <div className="mt-1 text-[11px] text-slate-400">weight sum {point.weight.toFixed(2)}</div>
                  )}
                </div>
              ))}
          </div>
        </div>
      )}
    </div>
  );
}

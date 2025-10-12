import { useCallback, useEffect, useMemo, useState } from "react";
import { axisClasses, ChartsAxisHighlight, ChartsTooltip, ChartsXAxis, ChartsYAxis, ResponsiveChartContainer } from "@mui/x-charts";
import { ScatterPlot } from "@mui/x-charts/ScatterChart";
import type { ChartsItemContentProps } from "@mui/x-charts/ChartsTooltip";
import type { ScatterValueType } from "@mui/x-charts/models/seriesType/scatter";

import { getHeatmap } from "../lib/api";
import type { HeatmapResp } from "../lib/types";

type Props = {
  bucketSeconds: number;
  columnCount: number;
  refreshToken: number;
};

const clamp = (value: number, min: number, max: number) => Math.min(Math.max(value, min), max);

const fmtSats = (n: number) => {
  if (n >= 100_000_000) return (n / 100_000_000).toFixed(2) + " BTC";
  if (n >= 1_000_000) return (n / 1_000_000).toFixed(1) + "M sats";
  if (n >= 1_000) return (n / 1_000).toFixed(1) + "k sats";
  return n.toString() + " sats";
};

const fmtTime = (ts: number) => new Date(ts * 1000).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit", second: "2-digit" });

const formatDuration = (seconds: number) => {
  if (seconds >= 3600) return `${(seconds / 3600).toFixed(1)} h`;
  if (seconds >= 60) return `${Math.round(seconds / 60)} min`;
  return `${seconds.toFixed(0)} s`;
};

const buildRowLabels = (edges: number[]) =>
  edges.map((edge, index) => {
    const next = edges[index + 1];
    if (next === undefined) return ">= " + fmtSats(edge);
    return fmtSats(edge) + " - " + fmtSats(Math.max(edge, next - 1));
  });

type ScatterPoint = { x: number; y: number; z?: number; id: string };
type PointMeta = {
  rowLabel: string;
  columnLabel: string;
  count: number;
  bucketStart: number;
  bucketEnd: number;
};

type ProcessedPayload = {
  rows: string[];
  columns: string[];
  points: ScatterPoint[];
  meta: PointMeta[];
  maxCount: number;
  totalSamples: number;
};

type WindowedPayload = {
  columns: string[];
  points: ScatterPoint[];
  meta: PointMeta[];
  size: number;
  offset: number;
  total: number;
  maxOffset: number;
};

const tooltipFactory = (meta: PointMeta[]) =>
  function HeatmapTooltip({ itemData, getColor }: ChartsItemContentProps<'scatter'>) {
    const entry = meta[itemData.dataIndex];
    if (!entry) return null;
    const windowLabel = fmtTime(entry.bucketStart) + " - " + fmtTime(entry.bucketEnd);
    const valueLabel = entry.count.toLocaleString();
    const swatch = getColor(itemData.dataIndex);
    return (
      <div className="min-w-[220px] space-y-2 rounded-xl border border-slate-700 bg-slate-900/90 px-4 py-3 text-xs text-slate-200 shadow-lg">
        <div className="flex items-center justify-between gap-3">
          <span className="font-semibold text-slate-100">{entry.rowLabel}</span>
          <span className="inline-flex items-center gap-2 text-slate-300">
            <span className="h-2.5 w-2.5 rounded-full" style={{ backgroundColor: swatch }} />
            {entry.columnLabel}
          </span>
        </div>
        <div className="flex items-center justify-between text-slate-300/90">
          <span>Outputs</span>
          <span className="font-semibold text-slate-50">{valueLabel}</span>
        </div>
        <div className="text-slate-400">{windowLabel}</div>
      </div>
    );
  };

export default function TransactionsHeatmap({ bucketSeconds, columnCount, refreshToken }: Props) {
  const [data, setData] = useState<HeatmapResp | null>(null);
  const [loading, setLoading] = useState(false);
  const [err, setErr] = useState<string | null>(null);
  const [windowSize, setWindowSize] = useState<number>(36);
  const [windowOffset, setWindowOffset] = useState<number>(0);

  const fetchIt = useCallback(async () => {
    setLoading(true);
    setErr(null);
    try {
      const resp = await getHeatmap({ bucket: bucketSeconds, buckets: columnCount });
      setData(resp);
    } catch (error: any) {
      setErr(error?.message ?? String(error));
      setData(null);
    } finally {
      setLoading(false);
    }
  }, [bucketSeconds, columnCount]);

  useEffect(() => {
    fetchIt();
  }, [fetchIt, refreshToken]);

  const processed = useMemo<ProcessedPayload>(() => {
    if (!data) {
      return { rows: [], columns: [], points: [], meta: [], maxCount: 0, totalSamples: 0 };
    }

    const rows = buildRowLabels(data.bin_edges);
    const columns = data.buckets.map((bucket) => fmtTime(bucket.end));
    const points: ScatterPoint[] = [];
    const meta: PointMeta[] = [];
    let maxCount = 0;

    data.buckets.forEach((bucket, colIndex) => {
      rows.forEach((rowLabel, rowIndex) => {
        const value = bucket.counts[rowIndex] ?? 0;
        if (value > maxCount) maxCount = value;
        points.push({ x: colIndex, y: rowIndex, z: value, id: colIndex + "-" + rowIndex });
        meta.push({
          rowLabel,
          columnLabel: columns[colIndex],
          count: value,
          bucketStart: bucket.start,
          bucketEnd: bucket.end,
        });
      });
    });

    return {
      rows,
      columns,
      points,
      meta,
      maxCount,
      totalSamples: data.total_samples,
    };
  }, [data]);

  useEffect(() => {
    const total = processed.columns.length;
    if (!total) {
      setWindowSize(0);
      setWindowOffset(0);
      return;
    }
    setWindowSize((prev) => {
      if (!prev) return Math.min(48, total);
      return clamp(prev, 1, total);
    });
  }, [processed.columns.length]);

  useEffect(() => {
    const total = processed.columns.length;
    if (!total) {
      setWindowOffset(0);
      return;
    }
    setWindowOffset((prev) => clamp(prev, 0, Math.max(0, total - Math.max(1, windowSize))));
  }, [processed.columns.length, windowSize]);

  const windowed = useMemo<WindowedPayload>(() => {
    const total = processed.columns.length;
    if (!total) {
      return { columns: [], points: [], meta: [], size: 0, offset: 0, total: 0, maxOffset: 0 };
    }
    const size = Math.max(1, Math.min(windowSize, total));
    const maxOffset = Math.max(0, total - size);
    const offset = clamp(windowOffset, 0, maxOffset);
    const columnLabels = processed.columns.slice(offset, offset + size);

    const points: ScatterPoint[] = [];
    const meta: PointMeta[] = [];
    processed.points.forEach((point, idx) => {
      if (point.x >= offset && point.x < offset + size) {
        points.push({ ...point, x: point.x - offset });
        const originalMeta = processed.meta[idx];
        meta.push({
          ...originalMeta,
          columnLabel: columnLabels[point.x - offset] ?? originalMeta.columnLabel,
        });
      }
    });

    return {
      columns: columnLabels,
      points,
      meta,
      size,
      offset,
      total,
      maxOffset,
    };
  }, [processed, windowSize, windowOffset]);

  const markerSize = useMemo(() => {
    if (!data || windowed.columns.length === 0 || processed.rows.length === 0) return 24;
    const maxWidth = Math.max(18, Math.min(60, 520 / windowed.columns.length));
    const maxHeight = Math.max(18, Math.min(70, 380 / processed.rows.length));
    return Math.min(maxWidth, maxHeight);
  }, [data, windowed.columns.length, processed.rows.length]);

  const chartHeight = useMemo(() => {
    if (processed.rows.length === 0) return 260;
    return Math.max(300, processed.rows.length * (markerSize + 8) + 140);
  }, [processed.rows.length, markerSize]);

  const xAxis = useMemo(() => [
    {
      id: "time",
      scaleType: "band" as const,
      data: windowed.columns.map((_, idx) => idx),
      valueFormatter: (value: number) => windowed.columns[value] ?? "",
      tickLabelPlacement: "middle" as const,
    },
  ], [windowed.columns]);

  const yAxis = useMemo(() => [
    {
      id: "bucket",
      scaleType: "band" as const,
      data: processed.rows.map((_, idx) => idx),
      valueFormatter: (value: number) => processed.rows[value] ?? "",
    },
  ], [processed.rows]);

  const zAxis = useMemo(() => [
    {
      id: "intensity",
      min: 0,
      max: Math.max(1, processed.maxCount),
      colorMap: {
        type: "continuous" as const,
        min: 0,
        max: Math.max(1, processed.maxCount),
        color: ["#1d4ed8", "#ec4899"] as const,
      },
    },
  ], [processed.maxCount]);

  const scatterSeries = useMemo(() => [
    {
      id: "mempool-heatmap",
      type: "scatter" as const,
      data: windowed.points,
      markerSize,
      xAxisId: "time",
      yAxisId: "bucket",
      zAxisId: "intensity",
      highlightScope: { highlight: "item", fade: "global" } as const,
      valueFormatter: (value: ScatterValueType) => `${(value.z ?? 0).toLocaleString()} outputs`,
    },
  ], [windowed.points, markerSize]);

  const HeatmapTooltipContent = useMemo(() => tooltipFactory(windowed.meta), [windowed.meta]);

  const infoLine = (
    <div className="text-sm text-slate-400">
      {loading && <span>Loading heatmap...</span>}
      {!loading && data && (
        <span>
          Samples {data.total_samples.toLocaleString()} | peak bucket {processed.maxCount.toLocaleString()} | bucket span {bucketSeconds}s | window {windowed.size} cols
        </span>
      )}
      {!loading && !data && !err && <span>No heatmap data.</span>}
    </div>
  );

  const sliderMin = Math.max(1, Math.min(12, windowed.total || 12));
  const sliderMax = Math.max(sliderMin, windowed.total || sliderMin);

  return (
    <div className="space-y-4">
      {infoLine}

      {err && (
        <div className="rounded-xl border border-rose-500/40 bg-rose-500/10 p-3 text-sm text-rose-200">{err}</div>
      )}

      {windowed.total > 0 && (
        <div className="flex flex-wrap items-center justify-between gap-3 text-xs text-slate-400">
          <div>
            Window {windowed.size} columns (~{formatDuration(windowed.size * bucketSeconds)})
          </div>
          <div className="flex items-center gap-2">
            <button
              type="button"
              onClick={() => setWindowOffset((prev) => clamp(prev - Math.max(1, Math.floor(windowed.size / 2)), 0, windowed.maxOffset))}
              className="rounded-full border border-slate-600/60 bg-slate-800/60 px-2 py-1 text-xs text-slate-200 transition hover:bg-slate-700"
              disabled={windowed.offset <= 0}
            >
              ◀
            </button>
            <button
              type="button"
              onClick={() => setWindowOffset((prev) => clamp(prev + Math.max(1, Math.floor(windowed.size / 2)), 0, windowed.maxOffset))}
              className="rounded-full border border-slate-600/60 bg-slate-800/60 px-2 py-1 text-xs text-slate-200 transition hover:bg-slate-700"
              disabled={windowed.offset >= windowed.maxOffset}
            >
              ▶
            </button>
            <input
              type="range"
              min={sliderMin}
              max={sliderMax}
              step={1}
              value={Math.max(sliderMin, Math.min(windowSize, sliderMax))}
              onChange={(event) => setWindowSize(Number(event.target.value))}
              className="w-32 accent-sky-400"
            />
            {windowed.maxOffset > 0 && (
              <input
                type="range"
                min={0}
                max={windowed.maxOffset}
                step={1}
                value={windowed.offset}
                onChange={(event) => setWindowOffset(Number(event.target.value))}
                className="w-32 accent-slate-400"
              />
            )}
          </div>
        </div>
      )}

      {windowed.points.length > 0 && (
        <div className="h-[360px] w-full" style={{ height: chartHeight }}>
          <ResponsiveChartContainer
            height={chartHeight}
            xAxis={xAxis}
            yAxis={yAxis}
            zAxis={zAxis}
            series={scatterSeries}
            margin={{ top: 20, right: 16, bottom: 64, left: 160 }}
            sx={{
              [`.${axisClasses.root}`]: { color: '#cbd5f5' },
              [`.${axisClasses.tickLabel}`]: { fill: '#cbd5f5', fontSize: 11 },
              [`.${axisClasses.label}`]: { fill: '#94a3b8', fontSize: 12 },
            }}
          >
            <ChartsXAxis position="bottom" axisId="time" label="Bucket end" />
            <ChartsYAxis position="left" axisId="bucket" label="Sats range" />
            <ChartsTooltip trigger="item" slots={{ itemContent: HeatmapTooltipContent }} />
            <ChartsAxisHighlight x="band" y="band" />
            <ScatterPlot />
          </ResponsiveChartContainer>
        </div>
      )}

      {processed.maxCount > 0 && (
        <div className="flex items-center gap-3 text-xs text-slate-400">
          <span>Low</span>
          <div className="h-2 flex-1 rounded-full bg-gradient-to-r from-[#1d4ed8] via-[#6366f1] to-[#ec4899]" />
          <span>High ({processed.maxCount.toLocaleString()})</span>
        </div>
      )}

      {windowed.points.length === 0 && !loading && !err && (
        <div className="rounded-xl border border-slate-700/60 bg-slate-900/60 p-6 text-sm text-slate-400">Heatmap will populate once the mempool cache has data.</div>
      )}

      {data?.overflow && (
        <div className="rounded-xl border border-amber-500/40 bg-amber-500/10 px-3 py-2 text-xs text-amber-200">
          Warning: outputs below the first bin were dropped.
        </div>
      )}
    </div>
  );
}

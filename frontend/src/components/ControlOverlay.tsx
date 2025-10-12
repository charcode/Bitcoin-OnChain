import React from "react";

const currency = new Intl.NumberFormat(undefined, {
  style: "currency",
  currency: "USD",
  maximumFractionDigits: 0,
});

const formatGrid = (value: number) => currency.format(value);

const formatSats = (value: number) => {
  if (value >= 100_000_000) return (value / 100_000_000).toFixed(2) + " BTC";
  if (value >= 1_000_000) return (value / 1_000_000).toFixed(1) + "M sats";
  if (value >= 1_000) return (value / 1_000).toFixed(1) + "k sats";
  return value.toLocaleString() + " sats";
};

type Props = {
  histGrid: number;
  histSpan: number;
  histMode: "count" | "weight_sum";
  bucketSeconds: number;
  columnCount: number;
  blockLookback: number;
  distSource: "mempool" | "blocks";
  distBinSize: number;
  distBinCount: number;
  distWeighted: boolean;
  distScale: "linear" | "sqrt" | "log";
  showRoundLines: boolean;
  gridOptions: number[];
  bucketOptions: number[];
  columnOptions: number[];
  blockOptions: number[];
  distSourceOptions: ("mempool" | "blocks")[];
  distBinSizeOptions: number[];
  distScaleOptions: ("linear" | "sqrt" | "log")[];
  onHistGridChange: (next: number) => void;
  onHistSpanChange: (next: number) => void;
  onHistModeChange: (next: "count" | "weight_sum") => void;
  onBucketChange: (next: number) => void;
  onColumnChange: (next: number) => void;
  onBlockLookbackChange: (next: number) => void;
  onDistSourceChange: (next: "mempool" | "blocks") => void;
  onDistBinSizeChange: (next: number) => void;
  onDistBinCountChange: (next: number) => void;
  onDistWeightedChange: (next: boolean) => void;
  onDistScaleChange: (next: "linear" | "sqrt" | "log") => void;
  onShowRoundLinesChange: (next: boolean) => void;
  onRefresh: () => void;
};

function optionIndex(options: number[], value: number) {
  const idx = options.indexOf(value);
  return idx === -1 ? 0 : idx;
}

const ControlOverlay: React.FC<Props> = ({
  histGrid,
  histSpan,
  histMode,
  bucketSeconds,
  columnCount,
  blockLookback,
  distSource,
  distBinSize,
  distBinCount,
  distWeighted,
  distScale,
  showRoundLines,
  gridOptions,
  bucketOptions,
  columnOptions,
  blockOptions,
  distSourceOptions,
  distBinSizeOptions,
  distScaleOptions,
  onHistGridChange,
  onHistSpanChange,
  onHistModeChange,
  onBucketChange,
  onColumnChange,
  onBlockLookbackChange,
  onDistSourceChange,
  onDistBinSizeChange,
  onDistBinCountChange,
  onDistWeightedChange,
  onDistScaleChange,
  onShowRoundLinesChange,
  onRefresh,
}) => {
  const gridIndex = optionIndex(gridOptions, histGrid);
  const bucketIndex = optionIndex(bucketOptions, bucketSeconds);
  const columnIndex = optionIndex(columnOptions, columnCount);
  const blockIndex = optionIndex(blockOptions, blockLookback);
  const distSizeIndex = optionIndex(distBinSizeOptions, distBinSize);

  const baseToggle = "flex-1 px-3 py-2 text-xs font-semibold uppercase tracking-wider transition";
  const countModeClasses =
    histMode === "count"
      ? `${baseToggle} bg-sky-400 text-slate-950 shadow`
      : `${baseToggle} bg-slate-800/60 text-slate-300 hover:bg-slate-800/90`;
  const weightModeClasses =
    histMode === "weight_sum"
      ? `${baseToggle} bg-sky-400 text-slate-950 shadow`
      : `${baseToggle} bg-slate-800/60 text-slate-300 hover:bg-slate-800/90`;

  const distToggleBase = "flex-1 px-3 py-2 text-xs font-semibold uppercase tracking-wider transition";

  return (
    <div className="space-y-8">
      <div className="space-y-2">
        <h2 className="text-xs font-semibold uppercase tracking-[0.35em] text-slate-300">Signal controls</h2>
        <p className="text-sm text-slate-400">Tune heatmaps, histograms, and distribution windows.</p>
      </div>

      <div className="grid gap-6 sm:grid-cols-2">
        <div className="space-y-2">
          <div className="text-xs uppercase tracking-wide text-slate-400">Histogram grid</div>
          <input
            type="range"
            min={0}
            max={gridOptions.length - 1}
            step={1}
            value={gridIndex}
            onChange={(event) => onHistGridChange(gridOptions[Number(event.target.value)])}
            className="w-full accent-sky-400"
          />
          <div className="text-base font-semibold text-sky-200">{formatGrid(histGrid)}</div>
        </div>

        <div className="space-y-2">
          <div className="text-xs uppercase tracking-wide text-slate-400">Histogram span (x anchor)</div>
          <input
            type="range"
            min={1}
            max={20}
            step={1}
            value={histSpan}
            onChange={(event) => onHistSpanChange(Number(event.target.value))}
            className="w-full accent-sky-400"
          />
          <div className="text-base font-semibold text-sky-200">x{histSpan}</div>
        </div>

        <div className="space-y-3 sm:col-span-2">
          <div className="text-xs uppercase tracking-wide text-slate-400">Histogram weighting</div>
          <div className="flex overflow-hidden rounded-full border border-slate-700/70 bg-slate-900/60">
            <button type="button" onClick={() => onHistModeChange("count")} className={countModeClasses}>
              Count
            </button>
            <button type="button" onClick={() => onHistModeChange("weight_sum")} className={weightModeClasses}>
              Weight
            </button>
          </div>
        </div>

        <div className="space-y-2">
          <div className="text-xs uppercase tracking-wide text-slate-400">Heatmap bucket (seconds)</div>
          <input
            type="range"
            min={0}
            max={bucketOptions.length - 1}
            step={1}
            value={bucketIndex}
            onChange={(event) => onBucketChange(bucketOptions[Number(event.target.value)])}
            className="w-full accent-indigo-400"
          />
          <div className="text-base font-semibold text-indigo-200">{bucketSeconds}s</div>
        </div>

        <div className="space-y-2">
          <div className="text-xs uppercase tracking-wide text-slate-400">Heatmap columns</div>
          <input
            type="range"
            min={0}
            max={columnOptions.length - 1}
            step={1}
            value={columnIndex}
            onChange={(event) => onColumnChange(columnOptions[Number(event.target.value)])}
            className="w-full accent-indigo-400"
          />
          <div className="text-base font-semibold text-indigo-200">{columnCount}</div>
        </div>

        <div className="space-y-2">
          <div className="text-xs uppercase tracking-wide text-slate-400">Historical lookback (blocks)</div>
          <input
            type="range"
            min={0}
            max={blockOptions.length - 1}
            step={1}
            value={blockIndex}
            onChange={(event) => onBlockLookbackChange(blockOptions[Number(event.target.value)])}
            className="w-full accent-violet-400"
          />
          <div className="text-base font-semibold text-violet-200">last {blockLookback.toLocaleString()} blocks</div>
        </div>

        <div className="space-y-3 sm:col-span-2">
          <div className="text-xs uppercase tracking-wide text-slate-400">Distribution source</div>
          <div className="flex overflow-hidden rounded-full border border-slate-700/70 bg-slate-900/60">
            {distSourceOptions.map((option) => {
              const active = distSource === option;
              const label = option === "mempool" ? "Mempool" : "Blocks";
              const cls = active
                ? `${distToggleBase} bg-emerald-300 text-slate-900 shadow`
                : `${distToggleBase} bg-slate-800/60 text-slate-200 hover:bg-slate-800/90`;
              return (
                <button key={option} type="button" className={cls} onClick={() => onDistSourceChange(option)}>
                  {label}
                </button>
              );
            })}
          </div>
          <div className="flex items-center justify-between gap-3 text-xs text-slate-300">
            <span>Weighted counts</span>
            <button
              type="button"
              onClick={() => onDistWeightedChange(!distWeighted)}
              className={`inline-flex items-center gap-2 rounded-full border px-3 py-1 transition ${
                distWeighted
                  ? "border-emerald-400/60 bg-emerald-500/20 text-emerald-100"
                  : "border-slate-700/70 bg-slate-800/60 text-slate-300 hover:bg-slate-800/80"
              }`}
            >
              <span className={`inline-block h-2.5 w-2.5 rounded-full ${distWeighted ? "bg-emerald-300" : "bg-slate-600"}`} />
              {distWeighted ? "On" : "Off"}
            </button>
          </div>
        </div>

        <div className="space-y-2">
          <div className="text-xs uppercase tracking-wide text-slate-400">Distribution bin size</div>
          <input
            type="range"
            min={0}
            max={Math.max(0, distBinSizeOptions.length - 1)}
            step={1}
            value={distSizeIndex}
            onChange={(event) =>
              onDistBinSizeChange(distBinSizeOptions[Math.min(distBinSizeOptions.length - 1, Number(event.target.value))])
            }
            className="w-full accent-emerald-400"
          />
          <div className="text-base font-semibold text-emerald-200">{formatSats(distBinSize)}</div>
        </div>

        <div className="space-y-2">
          <div className="text-xs uppercase tracking-wide text-slate-400">Distribution bins</div>
          <input
            type="range"
            min={10}
            max={200}
            step={5}
            value={distBinCount}
            onChange={(event) => onDistBinCountChange(Number(event.target.value))}
            className="w-full accent-emerald-400"
          />
          <div className="text-base font-semibold text-emerald-200">{distBinCount}</div>
        </div>

        <div className="space-y-2">
          <div className="text-xs uppercase tracking-wide text-slate-400">Distribution scale</div>
          <select
            value={distScale}
            onChange={(event) => onDistScaleChange(event.target.value as "linear" | "sqrt" | "log")}
            className="w-full rounded-2xl border border-slate-700/60 bg-slate-900/70 px-3 py-2 text-xs font-semibold uppercase tracking-wide text-slate-200"
          >
            {distScaleOptions.map((option) => (
              <option key={option} value={option}>
                {option === "linear" ? "Linear" : option === "sqrt" ? "Sqrt" : "Log"}
              </option>
            ))}
          </select>
        </div>

        <div className="space-y-2">
          <div className="text-xs uppercase tracking-wide text-slate-400">Round-USD anchors</div>
          <button
            type="button"
            onClick={() => onShowRoundLinesChange(!showRoundLines)}
            className={`w-full rounded-full px-4 py-2 text-xs font-semibold uppercase tracking-wide transition ${
              showRoundLines
                ? "border border-sky-400/60 bg-sky-500/20 text-sky-100"
                : "border border-slate-700/70 bg-slate-800/60 text-slate-300 hover:bg-slate-800/80"
            }`}
          >
            {showRoundLines ? "Visible" : "Hidden"}
          </button>
        </div>

        <div className="space-y-3">
          <div className="text-xs uppercase tracking-wide text-slate-400">Manual refresh</div>
          <button
            type="button"
            onClick={onRefresh}
            className="w-full rounded-full bg-sky-400 px-4 py-2 text-sm font-semibold text-slate-950 transition hover:bg-sky-300"
          >
            Refresh data
          </button>
        </div>
      </div>
    </div>
  );
};

export default ControlOverlay;

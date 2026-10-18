type Props = {
  histSpan: number;
  histMode: "count" | "weight_sum";
  bucketSeconds: number;
  columnCount: number;
  distSource: "mempool" | "blocks";
  distBinCount: number;
  distBinSize: number;
  distScale: "linear" | "sqrt" | "log";
  onHistSpanChange: (next: number) => void;
  onHistModeChange: (next: "count" | "weight_sum") => void;
  onBucketChange: (next: number) => void;
  onColumnChange: (next: number) => void;
  onDistSourceChange: (next: "mempool" | "blocks") => void;
  onDistBinCountChange: (next: number) => void;
  onDistBinSizeChange: (next: number) => void;
  onDistScaleChange: (next: "linear" | "sqrt" | "log") => void;
};

export default function AdvancedControlsPanel(props: Props) {
  return (
    <details className="surface-panel group">
      <summary className="cursor-pointer list-none px-5 py-4 md:px-6">
        <div className="flex items-center justify-between gap-4">
          <div>
            <div className="eyebrow">Advanced Model Controls</div>
            <div className="mt-2 text-lg font-semibold text-white">Tune diagnostics and expert views</div>
          </div>
          <div className="text-sm text-slate-400 transition group-open:rotate-180">⌄</div>
        </div>
      </summary>

      <div className="border-t border-white/6 px-5 py-5 md:px-6">
        <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-4">
          <label className="control-card">
            <span className="control-label">Histogram span</span>
            <input type="range" min={2} max={20} step={1} value={props.histSpan} onChange={(e) => props.onHistSpanChange(Number(e.target.value))} className="mt-4 w-full accent-sky-400" />
            <span className="mt-3 block text-white tabular-nums">x{props.histSpan}</span>
          </label>

          <div className="control-card">
            <span className="control-label">Anchor weighting</span>
            <div className="mt-4 flex overflow-hidden rounded-2xl border border-white/10">
              {(["count", "weight_sum"] as const).map((mode) => (
                <button
                  key={mode}
                  type="button"
                  onClick={() => props.onHistModeChange(mode)}
                  className={`flex-1 px-4 py-3 text-sm font-medium transition ${
                    props.histMode === mode ? "bg-sky-400/18 text-white" : "bg-transparent text-slate-300"
                  }`}
                >
                  {mode === "count" ? "Count" : "Weight"}
                </button>
              ))}
            </div>
          </div>

          <label className="control-card">
            <span className="control-label">Arrival step</span>
            <input type="range" min={15} max={300} step={15} value={props.bucketSeconds} onChange={(e) => props.onBucketChange(Number(e.target.value))} className="mt-4 w-full accent-fuchsia-400" />
            <span className="mt-3 block text-white tabular-nums">{props.bucketSeconds}s</span>
          </label>

          <label className="control-card">
            <span className="control-label">Timeline slices</span>
            <input type="range" min={12} max={72} step={6} value={props.columnCount} onChange={(e) => props.onColumnChange(Number(e.target.value))} className="mt-4 w-full accent-fuchsia-400" />
            <span className="mt-3 block text-white tabular-nums">{props.columnCount}</span>
          </label>

          <div className="control-card">
            <span className="control-label">Distribution source</span>
            <div className="mt-4 flex overflow-hidden rounded-2xl border border-white/10">
              {(["mempool", "blocks"] as const).map((source) => (
                <button
                  key={source}
                  type="button"
                  onClick={() => props.onDistSourceChange(source)}
                  className={`flex-1 px-4 py-3 text-sm font-medium capitalize transition ${
                    props.distSource === source ? "bg-emerald-400/18 text-white" : "text-slate-300"
                  }`}
                >
                  {source}
                </button>
              ))}
            </div>
          </div>

          <label className="control-card">
            <span className="control-label">Distribution bins</span>
            <input type="range" min={20} max={160} step={5} value={props.distBinCount} onChange={(e) => props.onDistBinCountChange(Number(e.target.value))} className="mt-4 w-full accent-emerald-400" />
            <span className="mt-3 block text-white tabular-nums">{props.distBinCount}</span>
          </label>

          <label className="control-card">
            <span className="control-label">Bin size</span>
            <input type="range" min={1000} max={5000000} step={1000} value={props.distBinSize} onChange={(e) => props.onDistBinSizeChange(Number(e.target.value))} className="mt-4 w-full accent-emerald-400" />
            <span className="mt-3 block text-white tabular-nums">{props.distBinSize.toLocaleString()} sats</span>
          </label>

          <label className="control-card">
            <span className="control-label">Distribution scale</span>
            <select value={props.distScale} onChange={(e) => props.onDistScaleChange(e.target.value as "linear" | "sqrt" | "log")} className="mt-4 w-full rounded-2xl border border-white/10 bg-slate-900/70 px-4 py-3 text-base text-white">
              <option value="linear">Linear</option>
              <option value="sqrt">Square root</option>
              <option value="log">Log</option>
            </select>
          </label>
        </div>
      </div>
    </details>
  );
}

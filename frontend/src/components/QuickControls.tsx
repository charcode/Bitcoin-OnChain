type Preset = "conservative" | "balanced" | "fast";

type Props = {
  lookback: number;
  grid: number;
  preset: Preset;
  onLookbackChange: (next: number) => void;
  onGridChange: (next: number) => void;
  onPresetChange: (next: Preset) => void;
  onRefresh: () => void;
};

const presets: { id: Preset; label: string; description: string }[] = [
  { id: "conservative", label: "Conservative", description: "Wider anchor context, slower signal read." },
  { id: "balanced", label: "Balanced", description: "Default view for resonance and concentration." },
  { id: "fast", label: "Fast", description: "Tighter anchor lens, faster local shifts." },
];

export default function QuickControls({ lookback, grid, preset, onLookbackChange, onGridChange, onPresetChange, onRefresh }: Props) {
  return (
    <section className="surface-panel p-5 md:p-6">
      <div className="flex flex-wrap items-start justify-between gap-4">
        <div>
          <div className="eyebrow">Quick Controls</div>
          <h2 className="mt-2 text-xl font-semibold text-white">Interpret the signal before tuning the model</h2>
          <p className="mt-2 text-sm leading-6 text-slate-300">
            Keep the defaults if you want the cleanest read. Use the expert controls only when you need to inspect a specific hypothesis.
          </p>
        </div>
        <button
          type="button"
          onClick={onRefresh}
          className="rounded-full border border-sky-400/40 bg-sky-400/12 px-4 py-2 text-sm font-medium text-sky-100 transition hover:bg-sky-400/18"
        >
          Refresh live data
        </button>
      </div>

      <div className="mt-6 grid gap-4 xl:grid-cols-[1.15fr_0.85fr_1.4fr]">
        <label className="control-card">
          <span className="control-label">Historical lookback</span>
          <input
            type="range"
            min={36}
            max={432}
            step={12}
            value={lookback}
            onChange={(event) => onLookbackChange(Number(event.target.value))}
            className="mt-4 w-full accent-sky-400"
          />
          <span className="mt-3 block text-lg font-semibold text-white tabular-nums">{lookback.toLocaleString()} blocks</span>
        </label>

        <label className="control-card">
          <span className="control-label">Anchor grid lens</span>
          <select
            value={grid}
            onChange={(event) => onGridChange(Number(event.target.value))}
            className="mt-4 w-full rounded-2xl border border-white/10 bg-slate-900/70 px-4 py-3 text-base text-white"
          >
            {[10, 25, 50, 100, 250, 500, 1000, 2000, 5000, 10000].map((option) => (
              <option key={option} value={option}>
                ${option.toLocaleString()}
              </option>
            ))}
          </select>
          <span className="mt-3 block text-sm text-slate-400">Defines which round-dollar spacing is emphasized in the concentration view.</span>
        </label>

        <div className="control-card">
          <span className="control-label">Sensitivity preset</span>
          <div className="mt-4 grid gap-3 md:grid-cols-3">
            {presets.map((entry) => {
              const active = preset === entry.id;
              return (
                <button
                  key={entry.id}
                  type="button"
                  onClick={() => onPresetChange(entry.id)}
                  className={`rounded-2xl border px-4 py-4 text-left transition ${
                    active
                      ? "border-fuchsia-400/45 bg-fuchsia-400/12 text-white shadow-[0_10px_30px_rgba(217,70,239,0.14)]"
                      : "border-white/8 bg-white/[0.03] text-slate-300 hover:bg-white/[0.06]"
                  }`}
                >
                  <div className="text-sm font-semibold">{entry.label}</div>
                  <div className="mt-2 text-xs leading-5 text-slate-400">{entry.description}</div>
                </button>
              );
            })}
          </div>
        </div>
      </div>
    </section>
  );
}

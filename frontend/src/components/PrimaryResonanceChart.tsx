import {
  Area,
  Bar,
  CartesianGrid,
  ComposedChart,
  Label,
  ReferenceArea,
  ReferenceLine,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";

import type { CurveResp, HistogramResp } from "../lib/types";

type Props = {
  curve: CurveResp | null;
  histogram: HistogramResp | null;
  livePrice: number | null;
  modelPrice: number | null;
  blendedPrice: number | null;
  confidence: number | null;
  updatedLabel: string;
};

const USD = new Intl.NumberFormat(undefined, {
  style: "currency",
  currency: "USD",
  maximumFractionDigits: 0,
});

export default function PrimaryResonanceChart({
  curve,
  histogram,
  livePrice,
  modelPrice,
  blendedPrice,
  confidence,
  updatedLabel,
}: Props) {
  const histogramMax = Math.max(...(histogram?.bins.map((bin) => bin.count) ?? [1]));
  void confidence;
  const confidenceValue = 0;
  const corridorHalfWidth =
    blendedPrice && blendedPrice > 0
      ? Math.max(blendedPrice * 0.004, (1 - confidenceValue) * blendedPrice * 0.018)
      : 0;

  const anchorLookup = new Map(
    (histogram?.bins ?? []).map((bin) => [Math.round(bin.price), { count: bin.count, weight: bin.weight_sum }])
  );

  const data = (curve?.points ?? []).map((point) => {
    const anchor = anchorLookup.get(Math.round(point.p));
    return {
      price: point.p,
      score: point.s,
      normalizedAnchor: anchor ? anchor.count / Math.max(1, histogramMax) : 0,
      anchorCount: anchor?.count ?? 0,
    };
  });

  const strongestAnchors = [...(histogram?.bins ?? [])]
    .sort((a, b) => b.count - a.count)
    .slice(0, 4);

  return (
    <section className="surface-panel p-5 md:p-6">
      <div className="flex flex-wrap items-start justify-between gap-4">
        <div>
          <div className="eyebrow">Primary Model View</div>
          <h2 className="mt-2 text-xl font-semibold text-white md:text-2xl">Legacy resonance curve</h2>
          <p className="mt-2 max-w-3xl text-sm leading-6 text-slate-300">
            The line shows resonance intensity across price space. Vertical anchor bars show where round-dollar concentration is strongest. Model-sensitivity bands and measured exchange errors are shown in the evaluation panel.
          </p>
        </div>
        <div className="rounded-full border border-white/10 bg-white/5 px-4 py-2 text-sm text-slate-300">
          Updated {updatedLabel}
        </div>
      </div>

      <div className="mt-6 grid gap-5 xl:grid-cols-[minmax(0,1.6fr)_320px]">
        <div className="chart-surface h-[430px] p-3 md:p-5">
          <ResponsiveContainer width="100%" height="100%">
            <ComposedChart data={data} margin={{ top: 12, right: 16, bottom: 8, left: 0 }}>
              <defs>
                <linearGradient id="resonanceFill" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="0%" stopColor="rgba(56,189,248,0.7)" />
                  <stop offset="100%" stopColor="rgba(56,189,248,0.05)" />
                </linearGradient>
              </defs>
              <CartesianGrid stroke="rgba(148,163,184,0.08)" vertical={false} />
              <XAxis
                dataKey="price"
                type="number"
                tick={{ fill: "#94a3b8", fontSize: 12 }}
                tickFormatter={(value) => `$${Math.round(value).toLocaleString()}`}
              />
              <YAxis
                yAxisId="score"
                tick={{ fill: "#94a3b8", fontSize: 12 }}
                tickFormatter={(value) => value.toFixed(2)}
                width={56}
              >
                <Label value="Resonance" angle={-90} position="insideLeft" fill="#94a3b8" style={{ textAnchor: "middle" }} />
              </YAxis>
              <YAxis yAxisId="anchor" orientation="right" hide domain={[0, 1]} />
              <Tooltip
                contentStyle={{ backgroundColor: "#081120", borderRadius: 18, border: "1px solid rgba(148,163,184,0.16)" }}
                labelFormatter={(value) => `Price ${USD.format(Number(value))}`}
                formatter={(value: number, key: string) => {
                  if (key === "score") return [value.toFixed(3), "Resonance"];
                  if (key === "anchorCount") return [Math.round(value).toLocaleString(), "Anchor concentration"];
                  return [value, key];
                }}
              />

              {blendedPrice && corridorHalfWidth > 0 && (
                <ReferenceArea
                  yAxisId="score"
                  x1={blendedPrice - corridorHalfWidth}
                  x2={blendedPrice + corridorHalfWidth}
                  fill="rgba(250,204,21,0.12)"
                  strokeOpacity={0}
                />
              )}

              <Bar
                yAxisId="anchor"
                dataKey="normalizedAnchor"
                fill="rgba(217,70,239,0.36)"
                barSize={6}
                radius={[4, 4, 0, 0]}
                animationDuration={450}
              />
              <Area
                yAxisId="score"
                type="monotone"
                dataKey="score"
                stroke="#38bdf8"
                strokeWidth={2.5}
                fill="url(#resonanceFill)"
                animationDuration={500}
              />

              {livePrice && (
                <ReferenceLine x={livePrice} yAxisId="score" stroke="#7dd3fc" strokeDasharray="4 4">
                  <Label value="Legacy model" fill="#7dd3fc" fontSize={12} position="top" />
                </ReferenceLine>
              )}
              {modelPrice && (
                <ReferenceLine x={modelPrice} yAxisId="score" stroke="#f0abfc" strokeDasharray="3 3">
                  <Label value="Nowcast" fill="#f0abfc" fontSize={12} position="top" />
                </ReferenceLine>
              )}
              {blendedPrice && (
                <ReferenceLine x={blendedPrice} yAxisId="score" stroke="#facc15" strokeWidth={2}>
                  <Label value="Blended estimate" fill="#fde68a" fontSize={12} position="top" />
                </ReferenceLine>
              )}
            </ComposedChart>
          </ResponsiveContainer>
        </div>

        <aside className="space-y-4">
          <div className="chart-surface p-4">
            <div className="text-xs font-medium uppercase tracking-[0.22em] text-slate-400">Reading the chart</div>
            <ul className="mt-4 space-y-3 text-sm leading-6 text-slate-300">
              <li><span className="font-medium text-slate-100">Blue curve:</span> resonance strength across the candidate price grid.</li>
              <li><span className="font-medium text-slate-100">Magenta bars:</span> round-dollar anchor concentration near the current estimate.</li>
              <li><span className="font-medium text-slate-100">Gold band:</span> disabled; see the measured candidate sensitivity band above.</li>
            </ul>
          </div>

          <div className="chart-surface p-4">
            <div className="text-xs font-medium uppercase tracking-[0.22em] text-slate-400">Strongest anchors</div>
            <div className="mt-4 space-y-3">
              {strongestAnchors.length === 0 && <div className="text-sm text-slate-400">Waiting for anchor concentration data.</div>}
              {strongestAnchors.map((anchor, index) => (
                <div key={anchor.price} className="rounded-2xl border border-white/8 bg-white/[0.03] px-4 py-3">
                  <div className="flex items-center justify-between gap-3">
                    <div>
                      <div className="text-sm font-semibold text-white">{USD.format(anchor.price)}</div>
                      <div className="text-xs text-slate-400">rank #{index + 1}</div>
                    </div>
                    <div className="text-right">
                      <div className="text-sm font-semibold text-fuchsia-300 tabular-nums">{anchor.count.toLocaleString()}</div>
                      <div className="text-xs text-slate-400">supporting outputs</div>
                    </div>
                  </div>
                </div>
              ))}
            </div>
          </div>
        </aside>
      </div>
    </section>
  );
}

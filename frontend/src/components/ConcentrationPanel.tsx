import type { HistogramResp } from "../lib/types";

type Props = {
  histogram: HistogramResp | null;
  mode: "count" | "weight_sum";
};

const USD = new Intl.NumberFormat(undefined, {
  style: "currency",
  currency: "USD",
  maximumFractionDigits: 0,
});

export default function ConcentrationPanel({ histogram, mode }: Props) {
  const items = [...(histogram?.bins ?? [])].sort((a, b) =>
    mode === "count" ? b.count - a.count : b.weight_sum - a.weight_sum
  );
  const maxValue = Math.max(...items.map((item) => (mode === "count" ? item.count : item.weight_sum)), 1);

  return (
    <section className="surface-panel p-5 md:p-6">
      <div className="flex flex-wrap items-start justify-between gap-4">
        <div>
          <div className="eyebrow">Anchor Concentration</div>
          <h2 className="mt-2 text-xl font-semibold text-white">Where transaction mass clusters around round USD levels</h2>
        </div>
        <div className="rounded-full border border-white/10 bg-white/5 px-4 py-2 text-sm text-slate-300">
          {histogram ? `${histogram.total_samples.toLocaleString()} samples` : "Waiting for histogram"}
        </div>
      </div>

      <div className="mt-6 space-y-3">
        {items.length === 0 && <div className="rounded-2xl border border-white/8 bg-white/[0.03] px-4 py-5 text-sm text-slate-400">No histogram data yet.</div>}
        {items.map((item) => {
          const value = mode === "count" ? item.count : item.weight_sum;
          const width = `${Math.max(4, (value / maxValue) * 100)}%`;
          return (
            <div key={item.price} className="rounded-2xl border border-white/8 bg-white/[0.03] px-4 py-3">
              <div className="flex items-center justify-between gap-3">
                <div className="text-sm font-semibold text-white">{USD.format(item.price)}</div>
                <div className="text-sm tabular-nums text-slate-300">
                  {mode === "count" ? item.count.toLocaleString() : item.weight_sum.toFixed(2)}
                </div>
              </div>
              <div className="mt-3 h-2.5 rounded-full bg-slate-900/90">
                <div className="h-full rounded-full bg-gradient-to-r from-fuchsia-500/70 to-sky-400/85" style={{ width }} />
              </div>
            </div>
          );
        })}
      </div>
    </section>
  );
}

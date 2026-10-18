import { useEffect, useState } from "react";
import axios from "axios";

type Model = { price?: number | null; status?: string; fresh?: boolean; error_usd?: number | null; error_pct?: number | null; lower?: number | null; upper?: number | null; reason?: string; age_sec?: number; matched_outputs?: number; anchor_count?: number };
type Quote = { price?: number | null; fresh?: boolean; status?: string; age_sec?: number | null; market_age_sec?: number | null; timestamp_kind?: string };
type Stats = { n: number; bias_usd: number | null; bias_pct: number | null; mae_usd: number | null; p95_abs_pct: number | null; band_coverage_pct: number | null };
type Evaluation = { legacy: Model; candidate: Model; reference: { price?: number | null; source_count?: number }; sources: Record<string, Quote>; statistics: { paired_n?: number; status?: string; paired_models?: Record<string, Stats> } };
const money = (v: number | null | undefined) => v == null ? "Unavailable" : new Intl.NumberFormat("en-US", { style: "currency", currency: "USD", maximumFractionDigits: 0 }).format(v);
const signed = (v: number | null | undefined, suffix = "") => v == null ? "—" : `${v >= 0 ? "+" : "−"}${Math.abs(v).toLocaleString("en-US", { maximumFractionDigits: 2 })}${suffix}`;
const plain = (v: number | null | undefined, suffix = "") => v == null ? "—" : `${v.toLocaleString("en-US", { maximumFractionDigits: 2 })}${suffix}`;

function SensitivityBand({ model, reference }: { model: Model; reference?: number | null }) {
  if (!model.fresh || model.price == null || model.lower == null || model.upper == null) return null;
  const lo = Math.min(model.lower, reference ?? model.lower) * .999;
  const hi = Math.max(model.upper, reference ?? model.upper) * 1.001;
  const x = (v: number) => 18 + (v - lo) / (hi - lo) * 564;
  return <div className="mt-4">
    <svg viewBox="0 0 600 55" className="w-full" role="img" aria-label="Candidate sensitivity band with exchange reference marker">
      <line x1="18" x2="582" y1="25" y2="25" stroke="#334155" strokeWidth="2" />
      <rect x={x(model.lower)} width={Math.max(1, x(model.upper) - x(model.lower))} y="12" height="26" rx="6" fill="#22d3ee" opacity=".3" />
      <circle cx={x(model.price)} cy="25" r="6" fill="#22d3ee"><title>Candidate {money(model.price)}</title></circle>
      {reference != null && <line x1={x(reference)} x2={x(reference)} y1="4" y2="46" stroke="#f8fafc" strokeWidth="3"><title>Exchange median {money(reference)}</title></line>}
    </svg>
    <p className="text-xs text-slate-400">Cyan: model sensitivity · White: exchange median, evaluation only</p>
  </div>;
}

export default function EvaluationPanel() {
  const [data, setData] = useState<Evaluation | null>(null);
  const [error, setError] = useState<string | null>(null);
  useEffect(() => {
    let active = true, running = false;
    const tick = async () => {
      if (running) return;
      running = true;
      try {
        const r = await axios.get<Evaluation>((import.meta.env.VITE_API_URL || "http://127.0.0.1:8000") + "/price/evaluation", { timeout: 6000 });
        if (active) { setData(r.data); setError(null); }
      } catch { if (active) { setData(null); setError("Evaluation unavailable. No current errors or bands can be verified."); } }
      finally { running = false; }
    };
    void tick(); const id = window.setInterval(tick, 5000);
    return () => { active = false; window.clearInterval(id); };
  }, []);
  const models = [["Legacy primary", data?.legacy], ["Refined candidate · shadow", data?.candidate]] as const;
  return <section className="surface-panel p-5 md:p-7" aria-label="Estimation errors and uncertainty">
    <div className="flex flex-wrap items-start justify-between gap-3">
      <div><div className="eyebrow">Accuracy monitor / USD benchmarks</div><h2 className="mt-2 text-2xl font-semibold">Estimation error & sensitivity</h2></div>
      <span className="rounded-full border border-amber-400/30 px-3 py-1 text-xs text-amber-200">Experimental · no accuracy guarantee</span>
    </div>
    <p className="mt-2 text-sm text-slate-400">Positive error means an overestimate. Exchange quotes evaluate the models; they never drive either estimate.</p>
    {error && <p role="alert" className="mt-4 text-amber-200">{error}</p>}
    <div className="mt-5 grid gap-4 md:grid-cols-3">
      <div className="chart-surface p-4"><p className="text-sm text-slate-400">Fresh USD exchange median</p><p className="mt-2 text-3xl font-semibold">{money(data?.reference.price)}</p><p className="mt-2 text-xs text-slate-400">{data?.reference.source_count ?? 0} fresh source(s) · last-trade quotes</p></div>
      {models.map(([label, model]) => <div className="chart-surface p-4" key={label}>
        <p className="text-sm text-slate-400">{label}</p><p className="mt-2 text-3xl font-semibold">{model?.fresh ? money(model.price) : "Unavailable / stale"}</p>
        <p className="mt-2 font-semibold text-amber-200">Error: {signed(model?.error_usd, " USD")} · {signed(model?.error_pct, "%")}</p>
        <p className="mt-2 text-xs text-slate-400">{model?.fresh ? `Model age ${plain(model.age_sec, "s")}` : model?.reason ?? "Waiting for fresh model data"}</p>
      </div>)}
    </div>
    <div className="mt-4 grid gap-5 lg:grid-cols-2">
      <div className="chart-surface p-4"><h3 className="font-semibold">Candidate sensitivity band</h3>
        <p className="mt-2 text-xl text-cyan-200">{data?.candidate.fresh ? `${money(data.candidate.lower)} – ${money(data.candidate.upper)}` : "Waiting for sufficient, unambiguous evidence"}</p>
        <p className="mt-2 text-xs text-slate-400">Sensitivity to three kernel widths around raw round-dollar evidence. This is not a 95% confidence interval or a predicted error bound.</p>
        {data && <SensitivityBand model={data.candidate} reference={data.reference.price} />}
        <p className="mt-3 text-xs text-slate-400">{data?.candidate.matched_outputs ?? 0} matched outputs · {data?.candidate.anchor_count ?? 0} anchor denominations · primary remains legacy pending validation</p>
      </div>
      <div className="chart-surface overflow-x-auto p-4"><h3 className="font-semibold">Exchange freshness</h3><table className="mt-3 w-full text-left text-sm"><thead className="text-slate-400"><tr><th>Source</th><th>BTC/USD</th><th>Retrieved</th><th>Status</th></tr></thead><tbody>
        {Object.entries(data?.sources ?? {}).map(([name, quote]) => <tr key={name} className="border-t border-white/10"><td className="py-3 capitalize">{name}</td><td>{money(quote.price)}</td><td>{plain(quote.age_sec, "s ago")}</td><td className={quote.fresh ? "text-emerald-300" : "text-amber-200"}>{quote.fresh ? "Fresh" : quote.status === "ok" ? "Stale" : quote.status}</td></tr>)}
      </tbody></table><p className="mt-2 text-xs text-slate-400">Retrieval age is not always trade age. Failed or stale sources are excluded. Model/quote skew must be ≤45s for an error measurement.</p></div>
    </div>
    <div className="mt-5 overflow-x-auto"><h3 className="font-semibold">24-hour paired errors · {data?.statistics.paired_n ?? 0} matched observations</h3>
      <p className="mt-1 text-xs text-slate-400">Same quote timestamps for both models. Early samples are not validation; band coverage is measured, not promised.</p>
      <table className="mt-3 w-full text-left text-sm"><thead className="text-slate-400"><tr><th>Model</th><th>Signed bias USD</th><th>Bias %</th><th>Mean absolute USD</th><th>95th absolute %</th><th>Reference inside band</th></tr></thead><tbody>
        {(["legacy", "candidate"] as const).map(name => { const s = data?.statistics.paired_models?.[name]; return <tr key={name} className="border-t border-white/10"><td className="py-3 capitalize">{name}</td><td>{signed(s?.bias_usd)}</td><td>{signed(s?.bias_pct, "%")}</td><td>{plain(s?.mae_usd)}</td><td>{plain(s?.p95_abs_pct, "%")}</td><td>{plain(s?.band_coverage_pct, "%")}</td></tr>; })}
      </tbody></table>
      <p className="mt-2 text-xs text-slate-400">Recorder: {data?.statistics.status ?? "waiting"} · references and paired errors persist for 14 days.</p>
    </div>
  </section>;
}

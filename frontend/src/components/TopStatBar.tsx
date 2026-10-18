import type { ReactNode } from "react";

export type StatItem = {
  label: string;
  value: string;
  tone?: "default" | "live" | "estimate" | "blend" | "confidence" | "warning";
  detail?: string;
};

type Props = {
  items: StatItem[];
  live: boolean;
  updatedAt: string;
  heroContent?: ReactNode;
  statusBanner?: ReactNode;
};

const toneClass: Record<NonNullable<StatItem["tone"]>, string> = {
  default: "text-slate-50",
  live: "text-sky-300",
  estimate: "text-fuchsia-300",
  blend: "text-amber-300",
  confidence: "text-emerald-300",
  warning: "text-rose-300",
};

export default function TopStatBar({ items, live, updatedAt, heroContent, statusBanner }: Props) {
  return (
    <section className="surface-panel overflow-hidden">
      <div className="flex flex-wrap items-start justify-between gap-4 border-b border-white/6 px-5 py-4 md:px-7">
        <div>
          <div className="eyebrow">Bitcoin Resonance Nowcast</div>
          <h1 className="mt-2 text-3xl font-semibold tracking-tight text-white md:text-4xl">
            On-chain estimation diagnostics
          </h1>
          <p className="mt-2 max-w-3xl text-sm leading-6 text-slate-300 md:text-base">
            Track where transaction concentration is forming, which round-dollar anchors are pulling hardest,
            with a legacy nowcast and separately evaluated experimental refinement.
          </p>
        </div>
        <div className="flex items-center gap-3 rounded-full border border-white/10 bg-white/5 px-4 py-2 text-sm">
          <span className={`h-2.5 w-2.5 rounded-full ${live ? "bg-emerald-400 shadow-[0_0_18px_rgba(74,222,128,0.8)]" : "bg-amber-400"}`} />
          <span className="font-medium text-slate-100">{live ? "Live" : "Polling paused"}</span>
          <span className="text-slate-400">Updated {updatedAt}</span>
        </div>
      </div>

      {statusBanner ? <div className="border-b border-white/6 px-5 py-4 md:px-7">{statusBanner}</div> : null}
      {heroContent ? <div className="border-b border-white/6 px-5 py-5 md:px-7">{heroContent}</div> : null}

      <div className="grid gap-px bg-white/6 md:grid-cols-3 xl:grid-cols-3">
        {items.map((item) => (
          <div key={item.label} className="bg-slate-950/40 px-5 py-5 md:px-6">
            <div className="text-xs font-medium uppercase tracking-[0.24em] text-slate-400">{item.label}</div>
            <div className={`mt-3 text-2xl font-semibold tabular-nums md:text-[2rem] ${toneClass[item.tone || "default"]}`}>
              {item.value}
            </div>
            {item.detail && <div className="mt-2 text-sm text-slate-400">{item.detail}</div>}
          </div>
        ))}
      </div>
    </section>
  );
}

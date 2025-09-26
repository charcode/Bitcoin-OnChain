import React from "react";
import type { PriceNow } from "../lib/types";

export default function PriceCards({ data }: { data: PriceNow | null }) {
  const price = data?.price ?? 0;
  const confPct = Math.round((data?.confidence ?? 0) * 100);
  const curvature = data?.curvature?.toFixed(3) ?? "—";
  const samples = data?.samples_used ?? 0;

  return (
    <section className="grid md:grid-cols-3 gap-4 mb-6">
      <div className="rounded-2xl p-5 bg-zinc-900 shadow">
        <div className="text-zinc-400 text-sm">Estimated Price</div>
        <div className="text-4xl font-bold mt-1">
          {price ? price.toLocaleString(undefined, { maximumFractionDigits: 2 }) : "—"}
        </div>
      </div>
      <div className="rounded-2xl p-5 bg-zinc-900 shadow">
        <div className="text-zinc-400 text-sm">Confidence</div>
        <div className="text-3xl font-semibold mt-1">{data ? `${confPct}%` : "—"}</div>
        <div className="text-xs text-zinc-500">Curvature: {curvature}</div>
      </div>
      <div className="rounded-2xl p-5 bg-zinc-900 shadow">
        <div className="text-zinc-400 text-sm">Samples</div>
        <div className="text-3xl font-semibold mt-1">{samples}</div>
      </div>
    </section>
  );
}

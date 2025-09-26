import React, { useMemo } from "react";
import type { CurveResp } from "../lib/types";
import { ResponsiveContainer, LineChart, Line, XAxis, YAxis, Tooltip, CartesianGrid } from "recharts";

export default function CurveChart({ curve }: { curve: CurveResp | null }) {
  const data = useMemo(() => (curve?.points || []).map(p => ({ price: p.p, score: p.s })), [curve]);

  return (
    <section className="rounded-2xl p-5 bg-zinc-900 shadow">
      <div className="flex items-end justify-between mb-3">
        <h2 className="text-xl font-semibold">Resonance Curve</h2>
        <div className="text-xs text-zinc-400">
          Updated {curve ? new Date(curve.t * 1000).toLocaleTimeString() : "—"} ({data.length} pts)
        </div>
      </div>
      <div className="h-72">
        <ResponsiveContainer width="100%" height="100%">
          <LineChart data={data}>
            <CartesianGrid strokeDasharray="3 3" />
            <XAxis dataKey="price" tickFormatter={(v: number) => v.toLocaleString()} />
            <YAxis />
            <Tooltip
              formatter={(v: number) => v.toFixed(2)}
              labelFormatter={(l: string) => `$${Number(l).toLocaleString()}`}
            />
            <Line type="monotone" dataKey="score" dot={false} />
          </LineChart>
        </ResponsiveContainer>
      </div>
      <p className="text-xs text-zinc-500 mt-2">Peak ≈ estimated price; sharper peak ⇒ higher confidence.</p>
    </section>
  );
}

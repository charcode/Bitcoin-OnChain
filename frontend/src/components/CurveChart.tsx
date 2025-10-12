import { useMemo } from "react";
import { ResponsiveContainer, LineChart, Line, XAxis, YAxis, Tooltip, CartesianGrid } from "recharts";

import type { CurveResp } from "../lib/types";

const axisTick = { fill: "#cbd5f5", fontSize: 11 } as const;

export default function CurveChart({ curve }: { curve: CurveResp | null }) {
  const data = useMemo(() => (curve?.points || []).map((p) => ({ price: p.p, score: p.s })), [curve]);
  const updatedLabel = curve
    ? new Date(curve.t * 1000).toLocaleTimeString([], {
        hour: "2-digit",
        minute: "2-digit",
        second: "2-digit",
      })
    : "waiting";

  return (
    <div className="space-y-4">
      <div className="flex flex-col gap-2 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <h2 className="text-xl font-semibold text-slate-50">Resonance curve</h2>
          <p className="text-sm text-slate-300/80">Baseline-subtracted score across the price grid.</p>
        </div>
        <div className="text-xs uppercase tracking-[0.3em] text-slate-400">
          {data.length.toLocaleString()} pts | updated {updatedLabel}
        </div>
      </div>
      <div className="h-72">
        <ResponsiveContainer width="100%" height="100%">
          <LineChart data={data} margin={{ top: 16, right: 20, bottom: 10, left: 10 }}>
            <CartesianGrid strokeDasharray="2 4" stroke="#1f2937" />
            <XAxis
              dataKey="price"
              tick={axisTick}
              tickFormatter={(value: number) => `$${Math.round(value).toLocaleString()}`}
            />
            <YAxis tick={axisTick} width={60} />
            <Tooltip
              contentStyle={{ backgroundColor: "#0f172a", borderRadius: 12, border: "1px solid #1f2937" }}
              formatter={(value: number) => Number(value).toFixed(3)}
              labelFormatter={(label: string) => `$${Number(label).toLocaleString()}`}
            />
            <Line type="monotone" dataKey="score" stroke="#38bdf8" strokeWidth={2} dot={false} />
          </LineChart>
        </ResponsiveContainer>
      </div>
      <div className="text-xs text-slate-400">Peaks highlight the strongest round-number resonance for the current window.</div>
    </div>
  );
}

import { CartesianGrid, Line, ResponsiveContainer, Tooltip, XAxis, YAxis, ComposedChart } from "recharts";

type Point = {
  t: number;
  live: number;
  blend: number;
  confidence: number;
};

type Props = {
  data: Point[];
};

const USD = new Intl.NumberFormat(undefined, {
  style: "currency",
  currency: "USD",
  maximumFractionDigits: 0,
});

export default function EstimateTimeline({ data }: Props) {
  return (
    <section className="surface-panel p-5 md:p-6">
      <div className="flex flex-wrap items-start justify-between gap-4">
        <div>
          <div className="eyebrow">Estimate Drift</div>
          <h2 className="mt-2 text-xl font-semibold text-white">Legacy nowcast history</h2>
        </div>
      </div>

      <div className="chart-surface mt-5 h-[280px] p-3 md:p-5">
        <ResponsiveContainer width="100%" height="100%">
          <ComposedChart data={data} margin={{ top: 12, right: 16, bottom: 8, left: 0 }}>
            <CartesianGrid stroke="rgba(148,163,184,0.08)" vertical={false} />
            <XAxis
              dataKey="t"
              tick={{ fill: "#94a3b8", fontSize: 12 }}
              tickFormatter={(value) => new Date(value).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" })}
            />
            <YAxis
              yAxisId="price"
              tick={{ fill: "#94a3b8", fontSize: 12 }}
              tickFormatter={(value) => `$${Math.round(value / 1000)}k`}
              width={56}
            />
            <YAxis yAxisId="confidence" orientation="right" hide domain={[0, 1]} />
            <Tooltip
              contentStyle={{ backgroundColor: "#081120", borderRadius: 18, border: "1px solid rgba(148,163,184,0.16)" }}
              labelFormatter={(value) => new Date(Number(value)).toLocaleTimeString()}
              formatter={(value: number, key: string) => {
                if (key === "confidence") return [`${Math.round(value * 100)}%`, "Confidence"];
                return [USD.format(value), key === "live" ? "Nowcast" : "Blended estimate"];
              }}
            />

            <Line yAxisId="price" type="monotone" dataKey="live" stroke="#7dd3fc" strokeWidth={2} dot={false} isAnimationActive={false} />

          </ComposedChart>
        </ResponsiveContainer>
      </div>
    </section>
  );
}

import { useCallback, useEffect, useMemo, useState } from "react";
import {
  Bar,
  BarChart,
  CartesianGrid,
  XAxis,
  YAxis,
  Tooltip,
  ResponsiveContainer,
  ReferenceLine,
  Legend,
} from "recharts";

type HistBin = { price: number; count: number; weight_sum: number };
type HistogramResp = {
  t: number;
  grid: number;
  span: number;
  window: number;
  used_price: number;
  bins: HistBin[];
  total_samples: number;
};

type Props = {
  apiBase?: string;
  grid: number;
  span: number;
  mode: "count" | "weight_sum";
  refreshToken: number;
};

const DEFAULT_BASE = "http://127.0.0.1:8000";

function fmtUSD(n: number) {
  if (!isFinite(n)) return "--";
  if (n >= 1000) return "$" + (n / 1000).toFixed(1) + "k";
  return "$" + n.toFixed(0);
}

function nearestAnchor(usedPrice: number, grid: number) {
  if (grid <= 0) return usedPrice;
  return Math.round(usedPrice / grid) * grid;
}

export default function RoundNumberHistogram({
  apiBase = DEFAULT_BASE,
  grid,
  span,
  mode,
  refreshToken,
}: Props) {
  const [loading, setLoading] = useState(false);
  const [err, setErr] = useState<string | null>(null);
  const [data, setData] = useState<HistogramResp | null>(null);

  const fetchHistogram = useCallback(async () => {
    setLoading(true);
    setErr(null);
    try {
      const url = apiBase + "/debug/histogram?grid=" + grid + "&span=" + span;
      const resp = await fetch(url);
      if (!resp.ok) {
        throw new Error(String(resp.status) + " " + resp.statusText);
      }
      const payload = (await resp.json()) as HistogramResp;
      setData(payload);
    } catch (error: any) {
      setErr(error?.message ?? String(error));
      setData(null);
    } finally {
      setLoading(false);
    }
  }, [apiBase, grid, span]);

  useEffect(() => {
    fetchHistogram();
  }, [fetchHistogram, refreshToken]);

  const center = useMemo(
    () => (data ? nearestAnchor(data.used_price, data.grid) : 0),
    [data]
  );

  const chartData = useMemo(() => {
    if (!data) return [] as Array<{ anchor: string; count: number; weight_sum: number }>;
    return data.bins.map((bin) => ({
      anchor: fmtUSD(bin.price),
      count: bin.count,
      weight_sum: bin.weight_sum,
    }));
  }, [data]);

  const legendLabel = mode === "count" ? "Count" : "Weight sum";
  const barFill = mode === "count" ? "#60a5fa" : "#fbbf24";

  return (
    <div className="space-y-4">
      <div className="text-sm text-slate-400">
        {loading && <span>Loading histogram...</span>}
        {!loading && data && (
          <span>
            Samples {data.total_samples.toLocaleString()} | window {fmtUSD(data.window)} | center {fmtUSD(center)}
          </span>
        )}
        {!loading && !data && !err && <span>No data available.</span>}
      </div>

      {err && <div className="rounded-xl border border-rose-500/40 bg-rose-500/10 p-3 text-sm text-red-300">{err}</div>}

      <div className="h-72 w-full">
        <ResponsiveContainer width="100%" height="100%">
          <BarChart data={chartData} margin={{ top: 10, right: 16, bottom: 10, left: 0 }}>
            <CartesianGrid strokeDasharray="2 2" stroke="#1f2937" />
            <XAxis
              dataKey="anchor"
              angle={-35}
              textAnchor="end"
              height={60}
              tick={{ fill: "#94a3b8", fontSize: 11 }}
            />
            <YAxis allowDecimals={false} tick={{ fill: "#94a3b8", fontSize: 11 }} />
            <Tooltip
              contentStyle={{ backgroundColor: "#09090b", borderRadius: 12, border: "1px solid #1f2937" }}
              formatter={(value: number) => value.toLocaleString()}
              labelFormatter={(label: string) => "Anchor " + label}
            />
            <Legend wrapperStyle={{ color: "#cbd5f5" }} />
            {data && (
              <ReferenceLine x={fmtUSD(center)} stroke="#fbbf24" strokeWidth={2} ifOverflow="extendDomain" />
            )}
            <Bar dataKey={mode} name={legendLabel} fill={barFill} radius={[6, 6, 0, 0]} />
          </BarChart>
        </ResponsiveContainer>
      </div>

      {data && (
        <div className="grid gap-2 text-xs text-slate-400 md:grid-cols-2">
          <div>Updated {new Date(data.t * 1000).toLocaleTimeString()}</div>
          <div>Grid {fmtUSD(data.grid)} | span x{span}</div>
          <div>Mode {legendLabel.toLowerCase()}</div>
          <div>Used price {fmtUSD(data.used_price)}</div>
        </div>
      )}
    </div>
  );
}

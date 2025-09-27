import { useEffect, useMemo, useState } from "react";
import {
  Bar, BarChart, CartesianGrid, XAxis, YAxis, Tooltip, ResponsiveContainer, ReferenceLine, Legend,
} from "recharts";

type HistBin = { price: number; count: number; weight_sum: number };
type HistogramResp = {
  t: number;
  grid: number;
  span: number;
  window: number;     // half-width used for inclusion around anchors
  used_price: number; // USD/BTC used to convert outputs
  bins: HistBin[];
  total_samples: number;
};

function fmtUSD(n: number) {
  if (!isFinite(n)) return "—";
  if (n >= 1000) return `$${(n/1000).toFixed(1)}k`;
  return `$${n.toFixed(0)}`;
}

function nearestAnchor(usedPrice: number, grid: number) {
  return Math.round(usedPrice / grid) * grid;
}

export default function RoundNumberHistogram({
  apiBase = "http://127.0.0.1:8000",
}: { apiBase?: string }) {
  const [grid, setGrid] = useState<number>(100);
  const [span, setSpan] = useState<number>(8);
  const [mode, setMode] = useState<"count" | "weight_sum">("count");
  const [loading, setLoading] = useState(false);
  const [err, setErr] = useState<string | null>(null);
  const [data, setData] = useState<HistogramResp | null>(null);

  const fetchIt = async () => {
    setLoading(true);
    setErr(null);
    try {
      const url = `${apiBase}/debug/histogram?grid=${grid}&span=${span}`;
      const r = await fetch(url);
      if (!r.ok) throw new Error(`${r.status} ${r.statusText}`);
      const j = (await r.json()) as HistogramResp;
      setData(j);
    } catch (e: any) {
      setErr(e?.message ?? String(e));
      setData(null);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => { fetchIt(); /* initial */ }, []); // eslint-disable-line
  useEffect(() => { fetchIt(); }, [grid, span]);     // refetch on controls

  const center = useMemo(
    () => (data ? nearestAnchor(data.used_price, data.grid) : 0),
    [data]
  );

  const chartData = useMemo(() => {
    if (!data) return [];
    // Keep the bins in order; map to a presentation-friendly shape
    return data.bins.map(b => ({
      anchor: b.price,
      label: fmtUSD(b.price),
      count: b.count,
      weight_sum: b.weight_sum,
    }));
  }, [data]);

  return (
    <div className="w-full space-y-4">
      <div className="flex flex-wrap items-end gap-3">
        <div className="flex flex-col">
          <label className="text-xs text-gray-500">Grid ($)</label>
          <select
            className="border rounded px-2 py-1"
            value={grid}
            onChange={e => setGrid(Number(e.target.value))}
          >
            {[10,25,50,100,250,500,1000,2000,5000,10000].map(g => (
              <option key={g} value={g}>{g}</option>
            ))}
          </select>
        </div>

        <div className="flex flex-col">
          <label className="text-xs text-gray-500">Span (± multiples)</label>
          <input
            type="range" min={1} max={20}
            value={span}
            onChange={e => setSpan(Number(e.target.value))}
          />
          <div className="text-xs text-gray-500">{span}</div>
        </div>

        <div className="flex items-center gap-2">
          <button
            className={`px-3 py-1 rounded border ${mode === "count" ? "bg-gray-100" : ""}`}
            onClick={() => setMode("count")}
          >
            Count
          </button>
          <button
            className={`px-3 py-1 rounded border ${mode === "weight_sum" ? "bg-gray-100" : ""}`}
            onClick={() => setMode("weight_sum")}
          >
            Weight
          </button>
        </div>

        <button
          onClick={fetchIt}
          className="ml-auto px-3 py-1 rounded bg-black text-white"
          disabled={loading}
        >
          {loading ? "Loading…" : "Refresh"}
        </button>
      </div>

      {err && <div className="text-red-600 text-sm">Error: {err}</div>}

      {data && (
        <>
          <div className="text-sm text-gray-600">
            Using price ≈ <b>{fmtUSD(data.used_price)}</b>, window ±<b>{fmtUSD(data.window)}</b> around each anchor.{" "}
            Samples: <b>{data.total_samples}</b>. Center anchor: <b>{fmtUSD(center)}</b>.
          </div>

          <div className="w-full h-72">
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={chartData} margin={{ top: 10, right: 16, bottom: 10, left: 0 }}>
                <CartesianGrid strokeDasharray="3 3" />
                <XAxis dataKey="label" angle={-35} textAnchor="end" height={60} />
                <YAxis allowDecimals={false} />
                <Tooltip
                  formatter={(val: any, name: any) =>
                    [val as number, name === "count" ? "Count" : "Weight sum"]
                  }
                  labelFormatter={(label: string) => `Anchor ${label}`}
                />
                <Legend />
                {/* Draw a vertical line at the center anchor */}
                <ReferenceLine x={fmtUSD(center)} strokeWidth={2} />
                <Bar dataKey={mode} name={mode === "count" ? "Count" : "Weight sum"} />
              </BarChart>
            </ResponsiveContainer>
          </div>
        </>
      )}
    </div>
  );
}

import { useEffect, useState } from "react";
import { getCandidates } from "../lib/api";
import type { CandidatesInfo } from "../lib/types";

export default function CandidatesPanel() {
  const [data, setData] = useState<CandidatesInfo | null>(null);
  const [loading, setLoading] = useState(false);

  const fetchNow = async () => {
    try {
      setLoading(true);
      const d = await getCandidates();
      setData(d);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    let alive = true;
    const tick = async () => {
      try {
        const d = await getCandidates();
        if (alive) setData(d);
      } catch {}
    };
    tick();
    const id = setInterval(tick, 5000);
    return () => {
      alive = false;
      clearInterval(id);
    };
  }, []);

  return (
    <div className="space-y-6">
      <div className="flex items-start justify-between gap-4">
        <div>
          <h3 className="text-xs font-semibold uppercase tracking-[0.35em] text-slate-300">Mempool coverage</h3>
          <p className="mt-1 text-sm text-slate-400">Live candidate counts from the cache.</p>
        </div>
        <button
          onClick={fetchNow}
          disabled={loading}
          className="rounded-full border border-slate-600/70 bg-slate-800/70 px-3 py-1.5 text-xs font-semibold uppercase tracking-wide text-slate-200 transition hover:bg-slate-700 disabled:opacity-60"
        >
          {loading ? "Refreshing..." : "Refresh"}
        </button>
      </div>

      <div className="grid gap-4 rounded-2xl border border-slate-700/60 bg-slate-900/70 p-5 text-sm text-slate-300">
        <div className="flex items-center justify-between">
          <span className="text-xs uppercase tracking-wide text-slate-400">Total outputs cached</span>
          <span className="text-lg font-semibold text-emerald-300">
            {data?.total_outputs_cached !== undefined ? data.total_outputs_cached.toLocaleString() : "--"}
          </span>
        </div>
        <div className="flex items-center justify-between">
          <span className="text-xs uppercase tracking-wide text-slate-400">Usable non-change</span>
          <span className="text-lg font-semibold text-sky-300">
            {data?.usable !== undefined ? data.usable.toLocaleString() : "--"}
          </span>
        </div>
        <div className="rounded-xl border border-slate-700/50 bg-slate-800/70 px-4 py-3 text-xs text-slate-400">
          Updated {new Date().toLocaleTimeString([], { hour: "2-digit", minute: "2-digit", second: "2-digit" })}
        </div>
      </div>
    </div>
  );
}

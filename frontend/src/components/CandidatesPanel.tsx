import React, { useEffect, useState } from "react";
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
    const id = setInterval(tick, 5000); // keep it visible & fresh
    return () => { alive = false; clearInterval(id); };
  }, []);

  return (
    <section className="rounded-2xl p-5 bg-zinc-900 shadow mb-6">
      <div className="flex items-center justify-between mb-2">
        <h2 className="text-xl font-semibold">Mempool Candidates</h2>
        <button
          onClick={fetchNow}
          disabled={loading}
          className="px-3 py-1.5 text-sm rounded-lg bg-zinc-800 hover:bg-zinc-700 disabled:opacity-50"
        >
          {loading ? "Refreshing..." : "Refresh"}
        </button>
      </div>
      <div className="text-sm text-zinc-300">
        <div>Total outputs cached: <span className="font-semibold">{data?.total_outputs_cached ?? "—"}</span></div>
        <div>Usable non-change: <span className="font-semibold">{data?.usable ?? "—"}</span></div>
      </div>
    </section>
  );
}

import React, { useState } from "react";
import { getPriceNow, getRnrCurve, getCandidates } from "../lib/api";

export default function DebugBar() {
  const [last, setLast] = useState<any>(null);
  const [err, setErr] = useState<string>("");

  const call = async (which: "price" | "curve" | "candidates") => {
    setErr("");
    try {
      if (which === "price") setLast(await getPriceNow());
      if (which === "curve") setLast(await getRnrCurve());
      if (which === "candidates") setLast(await getCandidates());
    } catch (e: any) {
      setErr(String(e?.message || e));
    }
  };

  return (
    <section className="rounded-2xl p-4 bg-zinc-900 shadow mb-6">
      <div className="flex items-center justify-between">
        <div className="font-semibold">Debug</div>
        <div className="text-xs text-zinc-400">
          API: {import.meta.env.VITE_API_URL || "http://127.0.0.1:8000"}
        </div>
      </div>
      <div className="mt-3 flex gap-2">
        <button onClick={() => call("price")} className="px-3 py-1.5 text-sm rounded-lg bg-zinc-800 hover:bg-zinc-700">/price/now</button>
        <button onClick={() => call("curve")} className="px-3 py-1.5 text-sm rounded-lg bg-zinc-800 hover:bg-zinc-700">/rnr/curve</button>
        <button onClick={() => call("candidates")} className="px-3 py-1.5 text-sm rounded-lg bg-zinc-800 hover:bg-zinc-700">/debug/candidates</button>
      </div>
      {err && <div className="mt-2 text-xs text-red-400">Error: {err}</div>}
      <pre className="mt-3 text-xs overflow-auto max-h-64">{last ? JSON.stringify(last, null, 2) : "—"}</pre>
    </section>
  );
}

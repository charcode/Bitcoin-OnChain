import { useEffect, useState } from "react";

import PriceCards from "./components/PriceCards";
import CurveChart from "./components/CurveChart";
import CandidatesPanel from "./components/CandidatesPanel";
import { getPriceNow, getRnrCurve } from "./lib/api";
import type { PriceNow, CurveResp } from "./lib/types";
import DebugBar from "./components/DebugBar";
import RoundNumberHistogram from "./components/RoundNumberHistogram";

export default function App() {
  const [price, setPrice] = useState<PriceNow | null>(null);
  const [curve, setCurve] = useState<CurveResp | null>(null);

  useEffect(() => {
    let alive = true;
    const tickPrice = async () => { try { const p = await getPriceNow(); if (alive) setPrice(p); } catch {} };
    const tickCurve = async () => { try { const c = await getRnrCurve(); if (alive) setCurve(c); } catch {} };
    tickPrice(); tickCurve();
    const id1 = setInterval(tickPrice, 2000);
    const id2 = setInterval(tickCurve, 4000);
    return () => { alive = false; clearInterval(id1); clearInterval(id2); };
  }, []);

  return (
    <div className="min-h-screen">
      <div className="max-w-6xl mx-auto p-6">
        <header className="mb-6">
          <h1 className="text-3xl font-semibold">btc-onchain — Live RNR Nowcaster</h1>
          <p className="text-zinc-400">Estimating price from mempool round-number resonance (no external feed).</p>
        </header>

        {/* Always visible candidates panel */}
        <CandidatesPanel />
        <DebugBar />
        <PriceCards data={price} />
        <CurveChart curve={curve} />

        {/* New: Round-number histogram */}
        <section className="mt-10">
          <h2 className="text-xl font-semibold mb-2">Round-number Histogram</h2>
          <RoundNumberHistogram apiBase="http://127.0.0.1:8000" />
        </section>
      </div>
    </div>
  );
}

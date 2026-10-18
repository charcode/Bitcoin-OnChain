import { useEffect, useRef, useState } from "react";

import EvaluationPanel from "./components/EvaluationPanel";
import AdvancedControlsPanel from "./components/AdvancedControlsPanel";
import ConcentrationPanel from "./components/ConcentrationPanel";
import EstimateTimeline from "./components/EstimateTimeline";
import MethodologyDrawer from "./components/MethodologyDrawer";
import PriceBanner from "./components/PriceBanner";
import PrimaryResonanceChart from "./components/PrimaryResonanceChart";
import QuickControls from "./components/QuickControls";
import TopStatBar from "./components/TopStatBar";
import type { StatItem } from "./components/TopStatBar";
import { getCandidates, getHistogram, getNodeStatus, getPriceNow, getRnrCurve, getStencilPrice } from "./lib/api";
import type { CandidatesInfo, CurveResp, HistogramResp, NodeStatus, PriceNow, StencilPriceResp } from "./lib/types";
import { usePriceStore } from "./state/usePriceStore";

type Preset = "conservative" | "balanced" | "fast";
type TimelinePoint = {
  t: number;
  live: number;
  blend: number;
  confidence: number;
};

const USD = new Intl.NumberFormat(undefined, {
  style: "currency",
  currency: "USD",
  maximumFractionDigits: 0,
});


function derivePresetConfig(preset: Preset) {
  if (preset === "conservative") return { grid: 500, span: 10 };
  if (preset === "fast") return { grid: 50, span: 6 };
  return { grid: 100, span: 8 };
}

export default function App() {
  const { setLatest } = usePriceStore();
  const [preset, setPreset] = useState<Preset>("balanced");
  const presetDefaults = derivePresetConfig(preset);

  const [blockLookback, setBlockLookback] = useState<number>(144);
  const [histGrid, setHistGrid] = useState<number>(presetDefaults.grid);
  const [histSpan, setHistSpan] = useState<number>(presetDefaults.span);
  const [histMode, setHistMode] = useState<"count" | "weight_sum">("count");
  const [bucketSeconds, setBucketSeconds] = useState<number>(60);
  const [columnCount, setColumnCount] = useState<number>(36);
  const [distSource, setDistSource] = useState<"mempool" | "blocks">("mempool");
  const [distBinCount, setDistBinCount] = useState<number>(60);
  const [distBinSize, setDistBinSize] = useState<number>(100_000);
  const distWeighted = false;
  const [distScale, setDistScale] = useState<"linear" | "sqrt" | "log">("linear");
  const [refreshToken, setRefreshToken] = useState<number>(0);

  const [nowcast, setNowcast] = useState<PriceNow | null>(null);
  const [nodeStatus, setNodeStatus] = useState<NodeStatus | null>(null);
  const [curve, setCurve] = useState<CurveResp | null>(null);
  const [histogram, setHistogram] = useState<HistogramResp | null>(null);
  const [stencil, setStencil] = useState<StencilPriceResp | null>(null);
  const [candidates, setCandidates] = useState<CandidatesInfo | null>(null);
  const [stencilLoading, setStencilLoading] = useState<boolean>(false);
  const [stencilError, setStencilError] = useState<string | null>(null);

  const livePrice = nowcast?.price != null && nowcast.price > 0 ? nowcast.price : null;

  const historyRef = useRef<TimelinePoint[]>([]);
  const [timelineHistory, setTimelineHistory] = useState<TimelinePoint[]>([]);

  useEffect(() => {
    setHistGrid(presetDefaults.grid);
    setHistSpan(presetDefaults.span);
  }, [presetDefaults.grid, presetDefaults.span]);

  useEffect(() => {
    let active = true;
    let inFlight = false;

    const tick = async () => {
      if (inFlight) return;
      inFlight = true;
      try {
        const [priceResp, candidatesResp, statusResp] = await Promise.all([getPriceNow(), getCandidates(), getNodeStatus()]);
        if (!active) return;
        setNowcast(priceResp);
        setNodeStatus(statusResp);
        const nextLivePrice = priceResp.price != null && priceResp.price > 0 ? priceResp.price : null;
        if (nextLivePrice !== null) {
          setLatest({
            ts: priceResp.t ? priceResp.t * 1000 : Date.now(),
            price: nextLivePrice,
            confidence: priceResp.confidence,
          });
        }
        setCandidates(candidatesResp);

        const blend = nextLivePrice ?? 0;

        if (nextLivePrice !== null || blend > 0) {
          const next: TimelinePoint = {
            t: Date.now(),
            live: nextLivePrice ?? 0,
            blend,
            confidence: priceResp.confidence || 0,
          };
          historyRef.current = [...historyRef.current, next].slice(-240);
          setTimelineHistory(historyRef.current);
        }
      } finally {
        inFlight = false;
      }
    };

    tick();
    const id = window.setInterval(tick, 2000);
    return () => {
      active = false;
      window.clearInterval(id);
    };
  }, [refreshToken, stencil]);

  useEffect(() => {
    let active = true;
    const run = async () => {
      try {
        const response = await getRnrCurve();
        if (active) setCurve(response);
      } catch {
        if (active) setCurve(null);
      }
    };
    run();
    const id = window.setInterval(run, 6000);
    return () => {
      active = false;
      window.clearInterval(id);
    };
  }, [refreshToken]);

  useEffect(() => {
    let active = true;
    const run = async () => {
      try {
        const response = await getHistogram({ grid: histGrid, span: histSpan });
        if (active) setHistogram(response);
      } catch {
        if (active) setHistogram(null);
      }
    };
    run();
    const id = window.setInterval(run, 6000);
    return () => {
      active = false;
      window.clearInterval(id);
    };
  }, [histGrid, histSpan, refreshToken]);

  useEffect(() => {
    let active = true;
    const run = async () => {
      setStencilLoading(true);
      try {
        const response = await getStencilPrice({ start: -Math.abs(blockLookback) });
        if (!active) return;
        setStencil(response);
        setStencilError(null);
      } catch (error) {
        if (!active) return;
        setStencil(null);
        setStencilError(error instanceof Error ? error.message : String(error));
      } finally {
        if (active) setStencilLoading(false);
      }
    };
    run();
    return () => {
      active = false;
    };
  }, [blockLookback, refreshToken]);

  const blend = null; // Historical estimates remain separate; no arbitrary blend.
  const lastUpdated = nowcast?.t
    ? new Date(nowcast.t * 1000).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit", second: "2-digit" })
    : "waiting";

  const topStats: StatItem[] = [
    {label: "Legacy nowcast", value: livePrice !== null ? USD.format(livePrice) : "--", tone: "estimate", detail: "Primary model retained during shadow validation"},
    {label: "Historical stencil", value: stencil?.estimated_price ? USD.format(stencil.estimated_price) : "--", detail: stencil ? `${stencil.block_count} blocks; different observation horizon` : "Waiting for historical sweep"},
    {label: "Rolling observations", value: nowcast ? nowcast.samples_used.toLocaleString() : "--", detail: "15-minute live output window; not independent trades"},
  ];

  const statusBanner = nodeStatus?.status === "missing" ? (
    <div className="rounded-2xl border border-rose-400/30 bg-rose-500/12 px-4 py-3 text-sm text-rose-100">
      <div className="font-semibold uppercase tracking-[0.18em] text-rose-300">Node missing</div>
      <div className="mt-1">{nodeStatus.message}</div>
    </div>
  ) : nodeStatus?.status === "not_ready" ? (
    <div className="rounded-2xl border border-amber-400/30 bg-amber-500/12 px-4 py-3 text-sm text-amber-100">
      <div className="font-semibold uppercase tracking-[0.18em] text-amber-300">Node not ready</div>
      <div className="mt-1">
        {nodeStatus.message}
        {nodeStatus.blocks != null || nodeStatus.headers != null ? ` ${nodeStatus.blocks ?? 0}/${nodeStatus.headers ?? 0} blocks loaded.` : ""}
      </div>
    </div>
  ) : null;

  return (
    <div className="min-h-screen bg-[radial-gradient(circle_at_top_left,rgba(56,189,248,0.12),transparent_34%),radial-gradient(circle_at_top_right,rgba(217,70,239,0.1),transparent_30%),linear-gradient(180deg,#06111f_0%,#030815_45%,#02060f_100%)] text-slate-100">
      <div className="mx-auto flex min-h-screen w-full max-w-[1600px] flex-col gap-6 px-4 py-5 md:px-6 lg:px-8">
        <EvaluationPanel />
        <TopStatBar items={topStats} live={!!nowcast?.t && Date.now()/1000 - nowcast.t < 30} updatedAt={lastUpdated} heroContent={<PriceBanner />} statusBanner={statusBanner} />

        <div className="grid gap-6 xl:grid-cols-[minmax(0,1.7fr)_minmax(320px,0.88fr)]">
          <div className="space-y-6">
            <PrimaryResonanceChart
              curve={curve}
              histogram={histogram}
              livePrice={nowcast?.price ?? null}
              modelPrice={null}
              blendedPrice={blend}
              confidence={nowcast?.confidence ?? null}
              updatedLabel={lastUpdated}
            />

            <div className="grid gap-6 xl:grid-cols-[minmax(0,1.2fr)_minmax(300px,0.8fr)]">
              <EstimateTimeline data={timelineHistory} />
              <ConcentrationPanel histogram={histogram} mode={histMode} />
            </div>

            <MethodologyDrawer
              candidates={candidates}
              stencil={stencil}
              stencilLoading={stencilLoading}
              stencilError={stencilError}
              blockLookback={blockLookback}
              bucketSeconds={bucketSeconds}
              columnCount={columnCount}
              refreshToken={refreshToken}
              distSource={distSource}
              distBinSize={distBinSize}
              distBinCount={distBinCount}
              distWeighted={distWeighted}
              distScale={distScale}
              priceUsd={livePrice}
            />
          </div>

          <div className="space-y-6">
            <QuickControls
              lookback={blockLookback}
              grid={histGrid}
              preset={preset}
              onLookbackChange={setBlockLookback}
              onGridChange={setHistGrid}
              onPresetChange={setPreset}
              onRefresh={() => setRefreshToken((token) => token + 1)}
            />

            <AdvancedControlsPanel
              histSpan={histSpan}
              histMode={histMode}
              bucketSeconds={bucketSeconds}
              columnCount={columnCount}
              distSource={distSource}
              distBinCount={distBinCount}
              distBinSize={distBinSize}
              distScale={distScale}
              onHistSpanChange={setHistSpan}
              onHistModeChange={setHistMode}
              onBucketChange={setBucketSeconds}
              onColumnChange={setColumnCount}
              onDistSourceChange={setDistSource}
              onDistBinCountChange={setDistBinCount}
              onDistBinSizeChange={setDistBinSize}
              onDistScaleChange={setDistScale}
            />

            <section className="surface-panel p-5 md:p-6">
              <div className="eyebrow">Method summary</div>
              <h2 className="mt-2 text-xl font-semibold text-white">How to read the model in five seconds</h2>
              <div className="mt-4 space-y-3 text-sm leading-6 text-slate-300">
                <p><span className="font-medium text-white">Transaction concentration</span> reveals where outputs are clustering in implied USD space.</p>
                <p><span className="font-medium text-white">Round-number anchors</span> show which psychological price levels are gathering the most support.</p>
                <p><span className="font-medium text-white">Resonance</span> is the curve produced when those anchors reinforce one another across the candidate price grid.</p>
                <p><span className="font-medium text-white">Confidence</span> rises when resonance sharpens and the estimate stabilizes.</p>
              </div>
            </section>
          </div>
        </div>
      </div>
    </div>
  );
}






import { useEffect, useState } from "react";

import ControlOverlay from "./components/ControlOverlay";
import PriceCards from "./components/PriceCards";
import RoundNumberHistogram from "./components/RoundNumberHistogram";
import TransactionsHeatmap from "./components/TransactionsHeatmap";
import RoundUsdHeatmap from "./components/RoundUsdHeatmap";
import SatsDistributionPanel from "./components/SatsDistributionPanel";
import CurveChart from "./components/CurveChart";
import CandidatesPanel from "./components/CandidatesPanel";
import { getPriceNow, getStencilPrice, getRnrCurve } from "./lib/api";
import type { PriceNow, StencilPriceResp, CurveResp } from "./lib/types";

const HIST_GRID_OPTIONS = [10, 25, 50, 100, 250, 500, 1000, 2000, 5000, 10000];
const HEAT_BUCKET_OPTIONS = [15, 30, 60, 120, 300];
const HEAT_COLUMN_OPTIONS = [12, 24, 36, 48, 72];
const BLOCK_LOOKBACK_OPTIONS = [36, 72, 144, 288, 432];
const DIST_SOURCE_OPTIONS: Array<"mempool" | "blocks"> = ["mempool", "blocks"];
const DIST_BIN_SIZE_OPTIONS = [1_000, 5_000, 10_000, 25_000, 50_000, 100_000, 250_000, 500_000, 1_000_000, 2_000_000, 5_000_000];
const DIST_SCALE_OPTIONS: Array<"linear" | "sqrt" | "log"> = ["linear", "sqrt", "log"];

const API_BASE = import.meta.env.VITE_API_URL || "http://127.0.0.1:8000";
const HERO_CURRENCY = new Intl.NumberFormat(undefined, {
  style: "currency",
  currency: "USD",
  maximumFractionDigits: 0,
});
const HERO_PERCENT = new Intl.NumberFormat(undefined, {
  style: "percent",
  maximumFractionDigits: 0,
});
const HERO_COMPACT = new Intl.NumberFormat(undefined, {
  notation: "compact",
  maximumFractionDigits: 1,
});

const formatSats = (value: number) => {
  if (value >= 100_000_000) return (value / 100_000_000).toFixed(2) + " BTC";
  if (value >= 1_000_000) return (value / 1_000_000).toFixed(1) + "M sats";
  if (value >= 1_000) return (value / 1_000).toFixed(1) + "k sats";
  return value.toLocaleString() + " sats";
};

export default function App() {
  const [nowcast, setNowcast] = useState<PriceNow | null>(null);
  const [histGrid, setHistGrid] = useState<number>(100);
  const [histSpan, setHistSpan] = useState<number>(8);
  const [histMode, setHistMode] = useState<"count" | "weight_sum">("count");
  const [bucketSeconds, setBucketSeconds] = useState<number>(60);
  const [columnCount, setColumnCount] = useState<number>(36);
  const [blockLookback, setBlockLookback] = useState<number>(144);
  const [refreshToken, setRefreshToken] = useState<number>(0);

  const defaultDistBinSize = DIST_BIN_SIZE_OPTIONS.includes(100_000)
    ? 100_000
    : DIST_BIN_SIZE_OPTIONS[Math.floor(DIST_BIN_SIZE_OPTIONS.length / 2)] ?? 100_000;
  const [distSource, setDistSource] = useState<"mempool" | "blocks">(DIST_SOURCE_OPTIONS[0]);
  const [distBinSize, setDistBinSize] = useState<number>(defaultDistBinSize);
  const [distBinCount, setDistBinCount] = useState<number>(60);
  const [distWeighted, setDistWeighted] = useState<boolean>(false);
  const [distScale, setDistScale] = useState<"linear" | "sqrt" | "log">("linear");
  const [showRoundLines, setShowRoundLines] = useState<boolean>(true);
  const [curve, setCurve] = useState<CurveResp | null>(null);

  const [stencil, setStencil] = useState<StencilPriceResp | null>(null);
  const [stencilLoading, setStencilLoading] = useState<boolean>(false);
  const [stencilError, setStencilError] = useState<string | null>(null);

  useEffect(() => {
    let alive = true;

    const tickPrice = async () => {
      try {
        const p = await getPriceNow();
        if (alive) setNowcast(p);
      } catch {
        // ignore transient errors
      }
    };

    tickPrice();
    const id = window.setInterval(tickPrice, 4000);
    return () => {
      alive = false;
      window.clearInterval(id);
    };
  }, []);

  useEffect(() => {
    let alive = true;

    const fetchStencil = async () => {
      setStencilLoading(true);
      try {
        const result = await getStencilPrice({ start: -Math.abs(blockLookback) });
        if (!alive) return;
        setStencil(result);
        setStencilError(null);
      } catch (err) {
        if (!alive) return;
        setStencil(null);
        setStencilError(err instanceof Error ? err.message : String(err));
      } finally {
        if (alive) setStencilLoading(false);
      }
    };

    fetchStencil();
    return () => {
      alive = false;
    };
  }, [blockLookback, refreshToken]);

  useEffect(() => {
    if (distSource === "blocks" && distWeighted) {
      setDistWeighted(false);
    }
  }, [distSource, distWeighted]);

  useEffect(() => {
    let alive = true;

    const fetchCurve = async () => {
      try {
        const response = await getRnrCurve();
        if (!alive) return;
        setCurve(response);
      } catch {
        if (!alive) return;
        setCurve(null);
      }
    };

    fetchCurve();
    const id = window.setInterval(fetchCurve, 6000);
    return () => {
      alive = false;
      window.clearInterval(id);
    };
  }, [refreshToken]);

  const handleRefresh = () => setRefreshToken((token) => token + 1);

  const heroPrice = nowcast?.price ?? null;
  const heroConfidence = nowcast?.confidence ?? null;
  const heroSamples = nowcast?.samples_used ?? null;
  const heroPriceLabel = heroPrice ? HERO_CURRENCY.format(heroPrice) : "--";
  const heroConfidenceLabel = heroConfidence !== null ? HERO_PERCENT.format(heroConfidence) : "--";
  const heroSamplesLabel = heroSamples !== null ? HERO_COMPACT.format(heroSamples) : "--";
  const heroLastUpdate = nowcast?.t
    ? new Date(nowcast.t * 1000).toLocaleTimeString([], {
        hour: "2-digit",
        minute: "2-digit",
        second: "2-digit",
      })
    : "waiting";
  const fulcrumEnabled = String(import.meta.env.VITE_FULCRUM_ENABLED ?? "true").toLowerCase() !== "false";

  return (
    <div className="relative min-h-screen overflow-x-hidden bg-slate-950 text-slate-100">
      <div className="gradient-orb gradient-orb--one" />
      <div className="gradient-orb gradient-orb--two" />
      <div className="grid-overlay" />
      <div className="relative mx-auto w-full max-w-screen-2xl px-6 pb-16 pt-12 lg:px-10">
        <header className="rounded-[32px] border border-slate-800/60 bg-slate-900/60 p-10 shadow-[0_40px_110px_rgba(4,8,35,0.55)] backdrop-blur">
          <div className="grid gap-10 lg:grid-cols-[minmax(0,1.75fr)_minmax(0,1fr)]">
            <div className="space-y-6">
              <span className="inline-flex items-center rounded-full border border-slate-500/30 bg-slate-500/10 px-4 py-1 text-xs font-semibold uppercase tracking-[0.3em] text-slate-200/80">
                On-chain resonance nowcasting
              </span>
              <h1 className="text-4xl font-semibold tracking-tight text-slate-50 sm:text-5xl lg:text-6xl">
                Live Bitcoin price inference from mempool and recent blocks
              </h1>
              <p className="max-w-2xl text-base leading-relaxed text-slate-200/80 sm:text-lg">
                Blend mempool round-number resonance with a calibrated historical sweep. Adjust sampling windows, compare live and anchor prices, and inspect how USD round amounts cluster over the last {blockLookback.toLocaleString()} blocks.
              </p>
              <div className="flex flex-wrap items-center gap-4 text-xs text-slate-200/70">
                <div className="rounded-full border border-slate-500/30 bg-slate-800/70 px-4 py-1">
                  Refresh cadence <span className="font-semibold text-slate-100">4s</span>
                </div>
                <div className="rounded-full border border-slate-500/30 bg-slate-800/70 px-4 py-1">
                  Fulcrum sweep <span className="font-semibold text-slate-100">{fulcrumEnabled ? "enabled" : "disabled"}</span>
                </div>
                <button
                  type="button"
                  onClick={handleRefresh}
                  className="rounded-full border border-sky-400/60 bg-sky-500/20 px-5 py-1.5 text-xs font-semibold uppercase tracking-wide text-sky-100 transition hover:border-sky-300 hover:bg-sky-500/30"
                >
                  Manual refresh
                </button>
              </div>
            </div>
            <div className="flex h-full items-end justify-end">
              <div className="w-full max-w-sm rounded-[28px] border border-slate-500/30 bg-slate-900/80 p-6 shadow-[0_20px_50px_rgba(2,6,23,0.55)]">
                <div className="text-xs font-semibold uppercase tracking-[0.25em] text-slate-400">Nowcaster snapshot</div>
                <div className="mt-5 space-y-4 text-sm text-slate-300/90">
                  <div className="flex items-baseline justify-between">
                    <span className="text-slate-300">Current price</span>
                    <span className="text-lg font-semibold text-sky-200">{heroPriceLabel}</span>
                  </div>
                  <div className="flex items-baseline justify-between">
                    <span className="text-slate-300">Confidence</span>
                    <span className="font-medium text-emerald-300">{heroConfidenceLabel}</span>
                  </div>
                  <div className="flex items-baseline justify-between">
                    <span className="text-slate-300">Mempool samples</span>
                    <span className="font-medium text-amber-300">{heroSamplesLabel}</span>
                  </div>
                  <div className="rounded-2xl border border-slate-600/40 bg-slate-800/80 px-4 py-2 text-xs text-slate-300/90">
                    Last refresh: {heroLastUpdate}
                  </div>
                </div>
              </div>
            </div>
          </div>
        </header>

        <main className="mt-12 grid gap-10 xl:grid-cols-[minmax(0,2.2fr)_minmax(320px,1fr)]">
          <div className="space-y-10">
            <section className="rounded-[28px] border border-slate-800/60 bg-slate-900/70 p-6 shadow-[0_20px_70px_rgba(4,6,25,0.55)]">
              <PriceCards
                nowcast={nowcast}
                stencil={stencil}
                blockLookback={blockLookback}
                stencilLoading={stencilLoading}
              />
            </section>

            <section className="rounded-[28px] border border-slate-800/60 bg-slate-900/70 p-6 shadow-[0_20px_70px_rgba(4,6,25,0.55)]">
              <CurveChart curve={curve} />
            </section>

            <section className="rounded-[28px] border border-slate-800/60 bg-slate-900/70 p-8 shadow-[0_20px_70px_rgba(4,6,25,0.5)]">
              <header className="mb-6 flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
                <div>
                  <h2 className="text-xl font-semibold text-slate-50">Historical round-number heatmap</h2>
                  <p className="text-sm text-slate-300/80">
                    Clusters of USD anchors derived from the latest {blockLookback.toLocaleString()} blocks.
                  </p>
                </div>
                <div className="text-xs uppercase tracking-[0.3em] text-slate-400">
                  {(stencil?.round_stats.length ?? 0).toLocaleString()} anchors | {stencil?.samples_used?.toLocaleString() ?? "--"} outputs
                </div>
              </header>
              <RoundUsdHeatmap
                stats={stencil?.round_stats ?? []}
                estimatedPrice={stencil?.estimated_price ?? null}
                samplesUsed={stencil?.samples_used ?? null}
                blockCount={stencil?.block_count ?? blockLookback}
                loading={stencilLoading}
                error={stencilError}
              />
            </section>

            <div className="grid gap-10 lg:grid-cols-2">
              <section className="rounded-[28px] border border-slate-800/60 bg-slate-900/70 p-6 shadow-[0_20px_70px_rgba(4,6,25,0.5)]">
                <header className="mb-6 flex items-center justify-between">
                  <h2 className="text-xl font-semibold text-slate-50">Round number output</h2>
                  <div className="text-xs uppercase tracking-[0.3em] text-slate-400">
                    grid {histGrid.toLocaleString()} | span x{histSpan} | mode {histMode === "count" ? "count" : "weight"}
                  </div>
                </header>
                <RoundNumberHistogram
                  apiBase={API_BASE}
                  grid={histGrid}
                  span={histSpan}
                  mode={histMode}
                  refreshToken={refreshToken}
                />
              </section>

              <section className="rounded-[28px] border border-slate-800/60 bg-slate-900/70 p-6 shadow-[0_20px_70px_rgba(4,6,25,0.5)]">
                <header className="mb-6 flex items-center justify-between">
                  <h2 className="text-xl font-semibold text-slate-50">Live mempool heatmap</h2>
                  <div className="text-xs uppercase tracking-[0.3em] text-slate-400">
                    bucket {bucketSeconds}s | columns {columnCount}
                  </div>
                </header>
                <TransactionsHeatmap
                  bucketSeconds={bucketSeconds}
                  columnCount={columnCount}
                  refreshToken={refreshToken}
                />
              </section>
            </div>

            <section className="rounded-[28px] border border-slate-800/60 bg-slate-900/70 p-6 shadow-[0_20px_70px_rgba(4,6,25,0.5)] lg:col-span-2">
              <header className="mb-6 flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
                <div>
                  <h2 className="text-xl font-semibold text-slate-50">Transaction size distribution</h2>
                  <p className="text-sm text-slate-300/80">Analyse how output amounts cluster in {distSource === "mempool" ? "the live mempool" : `the last ${blockLookback.toLocaleString()} blocks`}.</p>
                </div>
                <div className="text-xs uppercase tracking-[0.3em] text-slate-400">{distBinCount.toLocaleString()} bins | width {formatSats(distBinSize)}</div>
              </header>
              <SatsDistributionPanel
                source={distSource}
                binSize={distBinSize}
                binCount={distBinCount}
                blockLookback={blockLookback}
                weighted={distWeighted}
                scale={distScale}
                showRoundLines={showRoundLines}
                roundUsdAnchors={HIST_GRID_OPTIONS}
                priceUsd={nowcast?.price ?? null}
                refreshToken={refreshToken}
              />
            </section>

          </div>

          <aside className="space-y-10 xl:sticky xl:top-12">
            <section className="rounded-[28px] border border-slate-800/60 bg-slate-900/70 p-7 shadow-[0_20px_70px_rgba(4,6,25,0.55)]">
              <ControlOverlay
                histGrid={histGrid}
                histSpan={histSpan}
                histMode={histMode}
                bucketSeconds={bucketSeconds}
                columnCount={columnCount}
                blockLookback={blockLookback}
                distSource={distSource}
                distBinSize={distBinSize}
                distBinCount={distBinCount}
                distWeighted={distWeighted}
                distScale={distScale}
                showRoundLines={showRoundLines}
                gridOptions={HIST_GRID_OPTIONS}
                bucketOptions={HEAT_BUCKET_OPTIONS}
                columnOptions={HEAT_COLUMN_OPTIONS}
                blockOptions={BLOCK_LOOKBACK_OPTIONS}
                distSourceOptions={DIST_SOURCE_OPTIONS}
                distBinSizeOptions={DIST_BIN_SIZE_OPTIONS}
                distScaleOptions={DIST_SCALE_OPTIONS}
                onHistGridChange={setHistGrid}
                onHistSpanChange={setHistSpan}
                onHistModeChange={setHistMode}
                onBucketChange={setBucketSeconds}
                onColumnChange={setColumnCount}
                onBlockLookbackChange={setBlockLookback}
                onDistSourceChange={setDistSource}
                onDistBinSizeChange={setDistBinSize}
                onDistBinCountChange={(value) => setDistBinCount(Math.min(200, Math.max(10, value)))}
                onDistWeightedChange={setDistWeighted}
                onDistScaleChange={setDistScale}
                onShowRoundLinesChange={setShowRoundLines}
                onRefresh={handleRefresh}
              />
            </section>

            <section className="rounded-[28px] border border-slate-800/60 bg-slate-900/70 p-7 shadow-[0_20px_70px_rgba(4,6,25,0.55)]">
              <CandidatesPanel />
            </section>
          </aside>
        </main>
      </div>
    </div>
  );
}







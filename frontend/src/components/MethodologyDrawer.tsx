import type { CandidatesInfo, StencilPriceResp } from "../lib/types";
import RoundUsdHeatmap from "./RoundUsdHeatmap";
import SatsDistributionPanel from "./SatsDistributionPanel";
import TransactionsHeatmap from "./TransactionsHeatmap";

type Props = {
  candidates: CandidatesInfo | null;
  stencil: StencilPriceResp | null;
  stencilLoading: boolean;
  stencilError: string | null;
  blockLookback: number;
  bucketSeconds: number;
  columnCount: number;
  refreshToken: number;
  distSource: "mempool" | "blocks";
  distBinSize: number;
  distBinCount: number;
  distWeighted: boolean;
  distScale: "linear" | "sqrt" | "log";
  priceUsd: number | null;
};

export default function MethodologyDrawer(props: Props) {
  return (
    <details className="surface-panel group">
      <summary className="cursor-pointer list-none px-5 py-4 md:px-6">
        <div className="flex items-center justify-between gap-4">
          <div>
            <div className="eyebrow">Diagnostics And Methodology</div>
            <div className="mt-2 text-lg font-semibold text-white">Inspect raw concentration, live arrivals, and historical anchor context</div>
          </div>
          <div className="text-sm text-slate-400 transition group-open:rotate-180">⌄</div>
        </div>
      </summary>

      <div className="border-t border-white/6 px-5 py-5 md:px-6">
        <div className="grid gap-6 xl:grid-cols-[1.2fr_0.8fr]">
          <div className="space-y-6">
            <TransactionsHeatmap
              bucketSeconds={props.bucketSeconds}
              columnCount={props.columnCount}
              refreshToken={props.refreshToken}
            />
            <SatsDistributionPanel
              source={props.distSource}
              binSize={props.distBinSize}
              binCount={props.distBinCount}
              blockLookback={props.blockLookback}
              weighted={props.distWeighted}
              scale={props.distScale}
              showRoundLines={true}
              roundUsdAnchors={[10, 25, 50, 100, 250, 500, 1000, 2000, 5000, 10000]}
              priceUsd={props.priceUsd}
              refreshToken={props.refreshToken}
            />
          </div>

          <div className="space-y-6">
            <section className="chart-surface p-4">
              <div className="text-xs font-medium uppercase tracking-[0.22em] text-slate-400">Coverage</div>
              <div className="mt-4 grid gap-3 md:grid-cols-2 xl:grid-cols-1">
                <div className="rounded-2xl border border-white/8 bg-white/[0.03] px-4 py-4">
                  <div className="text-xs uppercase tracking-[0.22em] text-slate-400">Cached outputs</div>
                  <div className="mt-2 text-2xl font-semibold text-white tabular-nums">
                    {props.candidates?.total_outputs_cached?.toLocaleString() ?? "--"}
                  </div>
                </div>
                <div className="rounded-2xl border border-white/8 bg-white/[0.03] px-4 py-4">
                  <div className="text-xs uppercase tracking-[0.22em] text-slate-400">Usable outputs</div>
                  <div className="mt-2 text-2xl font-semibold text-white tabular-nums">
                    {props.candidates?.usable?.toLocaleString() ?? "--"}
                  </div>
                </div>
              </div>
            </section>

            <section className="chart-surface p-4">
              <div className="text-xs font-medium uppercase tracking-[0.22em] text-slate-400">Historical anchor map</div>
              <div className="mt-4">
                <RoundUsdHeatmap
                  stats={props.stencil?.round_stats ?? []}
                  estimatedPrice={props.stencil?.estimated_price ?? null}
                  samplesUsed={props.stencil?.samples_used ?? null}
                  blockCount={props.stencil?.block_count ?? props.blockLookback}
                  loading={props.stencilLoading}
                  error={props.stencilError}
                />
              </div>
            </section>
          </div>
        </div>
      </div>
    </details>
  );
}

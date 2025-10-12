import type { PriceNow, StencilPriceResp } from "../lib/types";

type Props = {
  nowcast: PriceNow | null;
  stencil: StencilPriceResp | null;
  blockLookback: number;
  stencilLoading?: boolean;
};

const usdFormatter = new Intl.NumberFormat(undefined, {
  style: "currency",
  currency: "USD",
  maximumFractionDigits: 0,
});

const signedUsdFormatter = new Intl.NumberFormat(undefined, {
  style: "currency",
  currency: "USD",
  maximumFractionDigits: 0,
  signDisplay: "always",
});

const signedPctFormatter = new Intl.NumberFormat(undefined, {
  style: "percent",
  maximumFractionDigits: 2,
  signDisplay: "always",
});

function fmtUSD(value: number | null | undefined) {
  if (value === null || value === undefined || !Number.isFinite(value)) return "--";
  return usdFormatter.format(value);
}

function fmtSignedUSD(value: number | null | undefined) {
  if (value === null || value === undefined || !Number.isFinite(value)) return "--";
  return signedUsdFormatter.format(value);
}

function fmtSignedPct(value: number | null | undefined) {
  if (value === null || value === undefined || !Number.isFinite(value)) return "--";
  return signedPctFormatter.format(value / 100);
}

export default function PriceCards({ nowcast, stencil, blockLookback, stencilLoading = false }: Props) {
  const priceNow = nowcast?.price ?? null;
  const confPct = nowcast ? Math.round(nowcast.confidence * 100) : null;
  const curvature = nowcast?.curvature ?? null;
  const mempoolSamples = nowcast?.samples_used ?? null;

  const stencilPrice = stencil?.estimated_price ?? null;
  const stencilSamples = stencil?.samples_used ?? null;

  let blendedPrice: number | null = null;
  if (priceNow && stencilPrice) {
    const weightNow = confPct ? Math.max(confPct / 100, 0.01) : 0.5;
    const weightStencil = 1;
    blendedPrice = (priceNow * weightNow + stencilPrice * weightStencil) / (weightNow + weightStencil);
  } else if (priceNow) {
    blendedPrice = priceNow;
  } else if (stencilPrice) {
    blendedPrice = stencilPrice;
  }

  const gap = priceNow && stencilPrice ? priceNow - stencilPrice : null;
  const gapPct = gap && stencilPrice ? (gap / stencilPrice) * 100 : null;

  const confLabel = confPct ?? 0;
  const curvatureLabel = (curvature ?? 0).toFixed(3);
  const mempoolSamplesLabel = mempoolSamples !== null && mempoolSamples !== undefined ? mempoolSamples.toLocaleString() : "--";
  const nowMeta = nowcast
    ? "confidence " + confLabel + "% | curvature " + curvatureLabel + " | " + mempoolSamplesLabel + " mempool samples"
    : "waiting for mempool";

  const stencilTitle = "Stencil price (last " + blockLookback.toLocaleString() + " blocks)";
  const stencilSamplesLabel = stencilSamples !== null && stencilSamples !== undefined ? stencilSamples.toLocaleString() : "--";
  const stencilMeta = stencil
    ? stencilSamplesLabel + " outputs | slide " + stencil.best_slide
    : stencilLoading
    ? "querying historical blocks..."
    : "pending (refresh)";

  const blendedMeta = priceNow && stencilPrice
    ? "weighted by confidence (" + confLabel + "%)"
    : priceNow
    ? "fallback to nowcaster"
    : stencilPrice
    ? "fallback to stencil"
    : "waiting";

  const gapAccent = gap !== null && gap < 0 ? "text-emerald-300" : "text-rose-300";
  const gapBackground = gap !== null && gap < 0
    ? "border border-emerald-400/25 bg-gradient-to-br from-emerald-500/15 via-slate-950/75 to-slate-950/90 shadow-[0_12px_32px_rgba(16,185,129,0.3)]"
    : "border border-rose-400/25 bg-gradient-to-br from-rose-500/15 via-slate-950/75 to-slate-950/90 shadow-[0_12px_32px_rgba(244,114,182,0.3)]";

  const cards = [
    {
      title: "Nowcaster price",
      value: fmtUSD(priceNow),
      meta: nowMeta,
      accent: "text-sky-200",
      background: "border border-sky-400/25 bg-gradient-to-br from-sky-500/15 via-slate-950/75 to-slate-950/90 shadow-[0_12px_32px_rgba(14,165,233,0.3)]",
    },
    {
      title: stencilTitle,
      value: stencilLoading ? "loading..." : fmtUSD(stencilPrice),
      meta: stencilMeta,
      accent: "text-indigo-200",
      background: "border border-indigo-400/25 bg-gradient-to-br from-indigo-500/15 via-slate-950/75 to-slate-950/90 shadow-[0_12px_32px_rgba(129,140,248,0.3)]",
    },
    {
      title: "Blended estimate",
      value: fmtUSD(blendedPrice),
      meta: blendedMeta,
      accent: "text-amber-200",
      background: "border border-amber-400/25 bg-gradient-to-br from-amber-500/15 via-slate-950/75 to-slate-950/90 shadow-[0_12px_32px_rgba(251,191,36,0.3)]",
    },
    {
      title: "Price gap",
      value: fmtSignedUSD(gap),
      meta: gapPct !== null && gapPct !== undefined ? fmtSignedPct(gapPct) : "requires both estimates",
      accent: gapAccent,
      background: gapBackground,
    },
  ];

  return (
    <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-4">
      {cards.map((card) => (
        <div
          key={card.title}
          className={`rounded-2xl p-5 backdrop-blur ${card.background}`}
        >
          <div className="text-xs uppercase tracking-[0.3em] text-slate-400">{card.title}</div>
          <div className={`mt-2 text-3xl font-semibold ${card.accent}`}>{card.value}</div>
          <div className="mt-3 text-xs text-slate-400">{card.meta}</div>
        </div>
      ))}
    </div>
  );
}

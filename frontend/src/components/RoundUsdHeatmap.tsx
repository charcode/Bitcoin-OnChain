import type { RoundUsdStat } from "../lib/types";

type Props = {
  stats: RoundUsdStat[];
  estimatedPrice: number | null;
  samplesUsed: number | null;
  blockCount: number;
  loading?: boolean;
  error?: string | null;
};

const currency = new Intl.NumberFormat(undefined, {
  style: "currency",
  currency: "USD",
  maximumFractionDigits: 0,
});

function colorFor(value: number, maxValue: number) {
  if (maxValue <= 0 || value <= 0) return "#0f172a";
  const ratio = Math.min(1, value / maxValue);
  const eased = Math.pow(ratio, 0.65);
  const start = { r: 37, g: 99, b: 235 }; // indigo-500
  const end = { r: 236, g: 72, b: 153 }; // pink-500
  const mix = {
    r: Math.round(start.r + (end.r - start.r) * eased),
    g: Math.round(start.g + (end.g - start.g) * eased),
    b: Math.round(start.b + (end.b - start.b) * eased),
  };
  const alpha = 0.18 + eased * 0.65;
  return `rgba(${mix.r}, ${mix.g}, ${mix.b}, ${alpha.toFixed(3)})`;
}

function formatNumber(n: number | null | undefined) {
  if (n === null || n === undefined || !Number.isFinite(n)) return "--";
  return n.toLocaleString();
}

export default function RoundUsdHeatmap({ stats, estimatedPrice, samplesUsed, blockCount, loading = false, error = null }: Props) {
  const sorted = [...stats].sort((a, b) => a.usd_amount - b.usd_amount);
  const maxRaw = sorted.reduce((acc, stat) => Math.max(acc, stat.raw_weight), 0);
  const priceLabel = estimatedPrice !== null && estimatedPrice !== undefined ? currency.format(estimatedPrice) : "--";

  return (
    <div className="space-y-5">
      <div className="flex flex-wrap items-center gap-4 text-sm text-slate-400">
        <span>{samplesUsed !== null && samplesUsed !== undefined ? formatNumber(samplesUsed) : "--"} outputs</span>
        <span>| window {blockCount.toLocaleString()} blocks</span>
        <span>| price anchor {priceLabel}</span>
        {loading && <span className="text-amber-300">loading historical data...</span>}
        {error && <span className="text-rose-400">{error}</span>}
      </div>

      <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
        {sorted.map((stat) => {
          const background = colorFor(stat.raw_weight, maxRaw);
          const border = stat.raw_weight > 0 ? "border-slate-700/60" : "border-slate-800/80";
          return (
            <div
              key={stat.usd_amount}
              className={`rounded-2xl border ${border} bg-slate-950/60 p-4 shadow-inner backdrop-blur`}
              style={{ backgroundColor: background }}
            >
              <div className="flex items-baseline justify-between">
                <span className="text-sm uppercase tracking-wide text-slate-200">{stat.usd_amount.toLocaleString()} USD</span>
                <span className="text-xs text-slate-200">{formatNumber(stat.raw_weight)} utxos</span>
              </div>
              <div className="mt-2 text-xs text-slate-200">
                sats {formatNumber(stat.sats)} | btc {stat.btc_amount.toPrecision(4)}
              </div>
              <div className="mt-1 text-xs text-slate-300">
                implied price {stat.implied_price ? currency.format(stat.implied_price) : "--"}
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}

import { useEffect, useMemo, useState } from "react";
import { usePriceStore } from "../state/usePriceStore.tsx";

const USD = new Intl.NumberFormat(undefined, {
  style: "currency",
  currency: "USD",
  maximumFractionDigits: 0,
});
const USD_SIGNED_0 = new Intl.NumberFormat(undefined, {
  style: "currency",
  currency: "USD",
  maximumFractionDigits: 0,
  signDisplay: "always",
});
const USD_SIGNED_2 = new Intl.NumberFormat(undefined, {
  style: "currency",
  currency: "USD",
  minimumFractionDigits: 2,
  maximumFractionDigits: 2,
  signDisplay: "always",
});
const PCT_SIGNED_2 = new Intl.NumberFormat(undefined, {
  style: "percent",
  maximumFractionDigits: 2,
  minimumFractionDigits: 2,
  signDisplay: "always",
});
const PCT_SIGNED_4 = new Intl.NumberFormat(undefined, {
  style: "percent",
  maximumFractionDigits: 4,
  minimumFractionDigits: 4,
  signDisplay: "always",
});

function formatTime(ts: number | undefined) {
  if (!ts || !Number.isFinite(ts)) return "Updated --";
  return new Date(ts).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit", second: "2-digit" });
}

export function getDeltaPct(prev?: number, curr?: number): number | undefined {
  if (prev == null || curr == null || prev === 0) return undefined;
  return ((curr - prev) / prev) * 100;
}

export function intensityFromPct(absPct: number): number {
  const capped = Math.min(Math.abs(absPct), 1.0);
  return Math.pow(capped, 0.6);
}

function colorFromDelta(prev?: number, curr?: number): { h: number; s: number; l: number; aText: number; aGlow: number } {
  const pct = getDeltaPct(prev, curr);
  if (pct === undefined || pct === 0) {
    return { h: 0, s: 0, l: 90, aText: 0.95, aGlow: 0.22 };
  }
  const up = pct > 0;
  const t = intensityFromPct(pct);
  const h = up ? 145 : 2; // greenish vs red
  const s = 90;
  const l = 65;
  // Visible floor so even $1 moves tint subtly
  const aText = Math.max(0.40, Math.min(1, t + 0.35));
  const aGlow = Math.min(0.35 + t * 0.3, 0.65);
  return { h, s, l, aText, aGlow };
}

export default function PriceBanner() {
  const { latest, previous, setLatest } = usePriceStore();

  const [flash, setFlash] = useState(false);
  // Trigger a brief flash animation when the price changes
  useEffect(() => {
    if (latest?.price == null) return;
    setFlash(true);
    const t = window.setTimeout(() => setFlash(false), 700);
    return () => window.clearTimeout(t);
  }, [latest?.price]);

  const price = latest?.price ?? null;
  const lastTs = latest?.ts;

  const base = useMemo(
    () => colorFromDelta(previous?.price, latest?.price),
    [previous?.price, latest?.price]
  );
  // Build legacy-compatible HSLA strings; boost alpha on flash
  const { textColor, glow } = useMemo(() => {
    const aText = Math.min(1, base.aText + (flash ? 0.25 : 0));
    const aGlow = Math.min(0.85, base.aGlow + (flash ? 0.25 : 0));
    const textColor = `hsla(${base.h}, ${base.s}%, ${base.l}%, ${aText})`;
    const glow = `hsla(${base.h}, ${base.s}%, ${base.l}%, ${aGlow})`;
    return { textColor, glow };
  }, [base, flash]);

  // Delta display (USD and percent) using same delta pipeline
  const prevPrice = previous?.price;
  const deltaAbs = prevPrice != null && price != null ? price - prevPrice : undefined;
  const deltaPct = prevPrice != null && price != null && prevPrice !== 0 ? (price - prevPrice) / prevPrice : undefined;
  const deltaUsdLabel = deltaAbs != null && isFinite(deltaAbs) ? USD_SIGNED_2.format(deltaAbs) : "--";
  const deltaPctLabel = deltaPct != null && isFinite(deltaPct) ? PCT_SIGNED_2.format(deltaPct) : "--";
  const deltaTextColor = deltaPct == null || deltaPct === 0 ? "hsla(0,0%,80%,0.85)" : textColor;

  const priceLabel = price !== null ? USD.format(price) : "--";
  const timeLabel = "Updated " + formatTime(lastTs);

  return (
    <div className="mt-4">
      <div
        className="select-none font-extrabold leading-none tracking-tight whitespace-nowrap tabular-nums flex flex-wrap items-baseline gap-x-3 gap-y-1"
        style={{
          color: textColor,
          textShadow: `0 0 22px ${glow}`,
          fontSize: "clamp(40px, 8vw, 88px)",
          lineHeight: 1.05,
          letterSpacing: "-0.02em",
          transform: flash ? "scale(1.02)" : "scale(1.0)",
          transition: "color 400ms ease, text-shadow 400ms ease, transform 220ms ease-out",
        }}
      >
        <span>{priceLabel}</span>
        <span
          className="font-semibold align-baseline"
          style={{ color: deltaTextColor, fontSize: "clamp(12px, 1.7vw, 16px)", transition: "color 400ms ease" }}
        >
          {deltaAbs != null && deltaPct != null ? `${deltaUsdLabel} (${deltaPctLabel})` : "--"}
        </span>
      </div>
      <div className="mt-2 text-slate-400" style={{ opacity: 0.8, fontSize: "clamp(12px, 1.7vw, 16px)" }}>{timeLabel}</div>

      {/* Debug controls removed; color pipeline driven purely by live updates */}
    </div>
  );
}

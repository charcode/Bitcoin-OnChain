import { useEffect, useMemo, useState } from "react";
import { usePriceStore } from "../state/usePriceStore.tsx";

const USD = new Intl.NumberFormat(undefined, {
  style: "currency",
  currency: "USD",
  maximumFractionDigits: 0,
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
  const aText = Math.max(0.35, Math.min(1, t + 0.35));
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

  const priceLabel = price !== null ? USD.format(price) : "--";
  const timeLabel = "Updated " + formatTime(lastTs);

  return (
    <div className="mt-4">
      <div
        className="select-none font-extrabold leading-none tracking-tight whitespace-nowrap tabular-nums"
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
        {priceLabel}
      </div>
      <div className="mt-2 text-slate-400" style={{ opacity: 0.8, fontSize: "clamp(12px, 1.7vw, 16px)" }}>{timeLabel}</div>

      {import.meta.env.DEV && (
        <div className="mt-3 flex flex-wrap items-center gap-2 text-[11px]">
          <span className="text-slate-400">Debug ticks:</span>
          {[
            { label: "-1.0%", factor: 0.99 },
            { label: "-0.3%", factor: 0.997 },
            { label: "+0.3%", factor: 1.003 },
            { label: "+1.0%", factor: 1.01 },
          ].map((btn) => (
            <button
              key={btn.label}
              type="button"
              className="rounded-full border border-slate-600/60 bg-slate-800/60 px-2.5 py-1 text-slate-200 hover:bg-slate-700"
              onClick={() => {
                // simulate a tick around the latest value
                const base = latest?.price ?? 100000;
                const next = Math.max(1, base * btn.factor);
                const ts = Date.now();
                setLatest({ ts, price: next, confidence: latest?.confidence });
              }}
            >
              {btn.label}
            </button>
          ))}
        </div>
      )}
    </div>
  );
}

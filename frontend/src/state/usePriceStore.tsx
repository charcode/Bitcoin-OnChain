import React, { createContext, useContext, useMemo, useRef, useState } from "react";

export type PricePoint = { ts: number; price: number; confidence?: number };

export interface PriceState {
  latest?: PricePoint;
  previous?: PricePoint;
  history: PricePoint[];
  setLatest: (p: PricePoint) => void;
  resetHistory: () => void;
}

const PriceStoreContext = createContext<PriceState | undefined>(undefined);

export function PriceStoreProvider({ children }: { children: React.ReactNode }) {
  const [latest, setLatestState] = useState<PricePoint | undefined>(undefined);
  const [previous, setPrevious] = useState<PricePoint | undefined>(undefined);
  const [history, setHistory] = useState<PricePoint[]>([]);
  const latestRef = useRef<PricePoint | undefined>(undefined);
  const previousRef = useRef<PricePoint | undefined>(undefined);
  const logCountRef = useRef<number>(0);

  const setLatest = (p: PricePoint) => {
    const prevLatest = latestRef.current;
    const hasPrev = !!prevLatest;
    const samePrice = hasPrev && prevLatest!.price === p.price;

    if (!hasPrev) {
      // First payload: seed both previous and latest to p; delta will be neutral until next tick
      setPrevious(p);
      previousRef.current = p;
      setLatestState(p);
      latestRef.current = p;
    } else if (samePrice) {
      // Price unchanged: update latest (ts/confidence) but do NOT promote previous
      setLatestState(p);
      latestRef.current = p;
    } else {
      // Price changed: promote previous to last latest, then set latest to new payload
      setPrevious(prevLatest!);
      previousRef.current = prevLatest!;
      setLatestState(p);
      latestRef.current = p;
    }
    setHistory((h) => {
      const next = [...h, p];
      // Dev-only diagnostics: log a few ticks to verify delta pipeline is numeric and ordered
      try {
        if (import.meta.env.DEV && logCountRef.current < 8) {
          const prevRaw = previousRef.current?.price;
          const latestRaw = latestRef.current?.price;
          const deltaRaw = prevRaw != null && latestRaw != null ? latestRaw - prevRaw : undefined;
          const deltaPct = prevRaw && latestRaw != null ? (latestRaw - prevRaw) / prevRaw : undefined;
          console.debug("[price-store]", { ts: p.ts, prevRaw, latestRaw, deltaRaw, deltaPct });
          logCountRef.current += 1;
        }
      } catch {}
      return next;
    });
  };

  const resetHistory = () => {
    setHistory([]);
  };

  const value = useMemo<PriceState>(
    () => ({ latest, previous, history, setLatest, resetHistory }),
    [latest, previous, history]
  );

  return (
    <PriceStoreContext.Provider value={value}>{children}</PriceStoreContext.Provider>
  );
}

export function usePriceStore(): PriceState {
  const ctx = useContext(PriceStoreContext);
  if (!ctx) throw new Error("usePriceStore must be used within PriceStoreProvider");
  return ctx;
}

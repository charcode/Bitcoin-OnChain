import React, { createContext, useContext, useMemo, useState } from "react";

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

  const setLatest = (p: PricePoint) => {
    setPrevious((prev) => (latest ? latest : prev));
    setLatestState(p);
    setHistory((h) => {
      const next = [...h, p];
      // Lightweight debug hook to verify session buffer behavior
      try { console.debug("[price-history] append", p); } catch {}
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


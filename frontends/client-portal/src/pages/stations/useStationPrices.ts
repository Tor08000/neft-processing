import { useCallback, useEffect, useRef, useState } from "react";
import { getStationPrices, type StationPriceItem } from "../../api/fuelStationsPrices";

const CACHE_TTL_MS = 5 * 60 * 1000;

type StationPricesCacheEntry = {
  items: StationPriceItem[];
  fetchedAt: number;
};

type StationPricesState = {
  status: "idle" | "loading" | "success" | "error";
  items: StationPriceItem[];
};

export function useStationPrices(stationId: string | null, token?: string | null) {
  const cacheRef = useRef<Map<string, StationPricesCacheEntry>>(new Map());
  const requestCounterRef = useRef(0);
  const [state, setState] = useState<StationPricesState>({ status: "idle", items: [] });

  const load = useCallback(
    async (force = false) => {
      if (!stationId || !token) {
        setState({ status: "idle", items: [] });
        return;
      }

      const now = Date.now();
      const cached = cacheRef.current.get(stationId);
      if (!force && cached && now - cached.fetchedAt < CACHE_TTL_MS) {
        setState({ status: "success", items: cached.items });
        return;
      }

      setState((prev) => ({ ...prev, status: "loading" }));
      const requestId = ++requestCounterRef.current;

      try {
        const response = await getStationPrices(token, stationId);
        if (requestId !== requestCounterRef.current) return;
        cacheRef.current.set(stationId, { items: response.items, fetchedAt: Date.now() });
        setState({ status: "success", items: response.items });
      } catch {
        if (requestId !== requestCounterRef.current) return;
        setState({ status: "error", items: [] });
      }
    },
    [stationId, token],
  );

  useEffect(() => {
    void load(false);
  }, [load]);

  const retry = useCallback(async () => {
    await load(true);
  }, [load]);

  const refresh = useCallback(async () => {
    await load(true);
  }, [load]);

  return {
    status: state.status,
    items: state.items,
    retry,
    refresh,
    load,
  };
}

export const stationPricesProductPriority = ["AI95", "AI92", "DT", "GAS"];

export function sortStationPrices(items: StationPriceItem[]): StationPriceItem[] {
  const order = new Map(stationPricesProductPriority.map((code, index) => [code, index]));
  return [...items].sort((a, b) => {
    const aRank = order.get(a.product_code) ?? Number.MAX_SAFE_INTEGER;
    const bRank = order.get(b.product_code) ?? Number.MAX_SAFE_INTEGER;
    if (aRank !== bRank) return aRank - bRank;
    return a.product_code.localeCompare(b.product_code);
  });
}

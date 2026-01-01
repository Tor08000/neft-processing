import { useEffect, useState } from "react";

export type TableDensity = "compact" | "comfortable";

const STORAGE_KEY = "neft.tableDensity.client";
const DEFAULT_DENSITY: TableDensity = "comfortable";

export function useTableDensity() {
  const [density, setDensity] = useState<TableDensity>(() => {
    if (typeof window === "undefined") return DEFAULT_DENSITY;
    const saved = window.localStorage.getItem(STORAGE_KEY);
    if (saved === "compact" || saved === "comfortable") return saved;
    return DEFAULT_DENSITY;
  });

  useEffect(() => {
    if (typeof window === "undefined") return;
    window.localStorage.setItem(STORAGE_KEY, density);
  }, [density]);

  return { density, setDensity };
}

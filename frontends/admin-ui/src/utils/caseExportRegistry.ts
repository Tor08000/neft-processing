export type CaseExportType = "explain" | "diff" | "case";

export type CaseExportRegistryItem = {
  id: string;
  created_at: string;
  case_id?: string | null;
  type: CaseExportType;
};

const STORAGE_KEY = "neft_admin_case_exports_v1";
const MAX_ENTRIES = 200;

const isRecord = (value: unknown): value is Record<string, unknown> => typeof value === "object" && value !== null;

const normalizeString = (value: unknown): string | null => (typeof value === "string" ? value : null);

const normalizeExportType = (value: unknown): CaseExportType | null => {
  if (value === "explain" || value === "diff" || value === "case") return value;
  return null;
};

const normalizeEntry = (entry: unknown): CaseExportRegistryItem | null => {
  if (!isRecord(entry)) return null;
  const id = normalizeString(entry.id);
  const created_at = normalizeString(entry.created_at);
  const type = normalizeExportType(entry.type);
  if (!id || !created_at || !type) return null;
  const caseId = normalizeString(entry.case_id);
  return { id, created_at, type, case_id: caseId ?? undefined };
};

const generateId = (): string => {
  if (typeof crypto !== "undefined" && "randomUUID" in crypto) {
    return crypto.randomUUID();
  }
  return `exp_${Date.now()}_${Math.random().toString(16).slice(2)}`;
};

const loadAll = (): CaseExportRegistryItem[] => {
  if (typeof window === "undefined" || !window.localStorage) return [];
  try {
    const raw = window.localStorage.getItem(STORAGE_KEY);
    if (!raw) return [];
    const parsed = JSON.parse(raw) as unknown[];
    return (parsed ?? []).map(normalizeEntry).filter((item): item is CaseExportRegistryItem => Boolean(item));
  } catch {
    return [];
  }
};

const saveAll = (items: CaseExportRegistryItem[]) => {
  if (typeof window === "undefined" || !window.localStorage) return;
  window.localStorage.setItem(STORAGE_KEY, JSON.stringify(items));
};

export const loadCaseExports = (): CaseExportRegistryItem[] => loadAll();

export const recordCaseExport = (options: {
  caseId?: string | null;
  type: CaseExportType;
}): CaseExportRegistryItem | null => {
  if (typeof window === "undefined" || !window.localStorage) return null;
  const entry: CaseExportRegistryItem = {
    id: generateId(),
    created_at: new Date().toISOString(),
    case_id: options.caseId ?? undefined,
    type: options.type,
  };
  const updated = [...loadAll(), entry].slice(-MAX_ENTRIES);
  saveAll(updated);
  return entry;
};

export type DatePreset = "7d" | "30d" | "90d" | "mtd" | "custom";

export const buildDateRange = (preset: DatePreset): { from: string; to: string } => {
  const toDate = new Date();
  const fromDate = new Date();
  if (preset === "7d") {
    fromDate.setDate(toDate.getDate() - 7);
  } else if (preset === "30d") {
    fromDate.setDate(toDate.getDate() - 30);
  } else if (preset === "90d") {
    fromDate.setDate(toDate.getDate() - 90);
  } else if (preset === "mtd") {
    fromDate.setDate(1);
  }
  return { from: fromDate.toISOString().slice(0, 10), to: toDate.toISOString().slice(0, 10) };
};

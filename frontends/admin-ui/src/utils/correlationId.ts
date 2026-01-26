export const createCorrelationId = (): string => {
  if (typeof crypto !== "undefined" && "randomUUID" in crypto) {
    return crypto.randomUUID();
  }
  const random = Math.random().toString(36).slice(2, 10);
  return `corr_${Date.now().toString(36)}_${random}`;
};

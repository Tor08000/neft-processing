export const extractRequestId = (error: unknown): string | null => {
  if (!error) return null;
  const message = error instanceof Error ? error.message : String(error);
  const jsonStart = message.indexOf("{");
  if (jsonStart >= 0) {
    const candidate = message.slice(jsonStart);
    try {
      const parsed = JSON.parse(candidate) as { request_id?: string };
      if (parsed.request_id) {
        return parsed.request_id;
      }
    } catch {
      // ignore parsing errors
    }
  }
  const match = message.match(/request_id\"\\s*:\\s*\"([^\"]+)/);
  return match?.[1] ?? null;
};

export const buildPlaceholderLink = (title: string) => `/ops/drilldown?title=${encodeURIComponent(title)}`;

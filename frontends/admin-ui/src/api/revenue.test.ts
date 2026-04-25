import { describe, expect, it, vi } from "vitest";

import { fetchOverdueList, fetchRevenueSummary } from "./revenue";
import { request } from "./http";

vi.mock("./http", () => ({
  request: vi.fn(),
}));

describe("revenue API", () => {
  it("uses the canonical admin revenue summary route under the shared admin API base", async () => {
    vi.mocked(request).mockResolvedValueOnce({} as never);

    await fetchRevenueSummary("2026-04-23", "token-1");

    expect(request).toHaveBeenCalledWith("/revenue/summary?as_of=2026-04-23", {}, "token-1");
  });

  it("uses the canonical admin revenue overdue route under the shared admin API base", async () => {
    vi.mocked(request).mockResolvedValueOnce({} as never);

    await fetchOverdueList({ bucket: "31_90", limit: 20, offset: 40, asOf: "2026-04-23" }, "token-1");

    expect(request).toHaveBeenCalledWith(
      "/revenue/overdue?bucket=31_90&limit=20&offset=40&as_of=2026-04-23",
      {},
      "token-1",
    );
  });
});

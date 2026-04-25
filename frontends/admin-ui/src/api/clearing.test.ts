import { beforeEach, describe, expect, it, vi } from "vitest";

import { apiGet } from "./client";
import { fetchClearingBatchDetails, fetchClearingBatches } from "./clearing";

vi.mock("./client", () => ({
  apiGet: vi.fn(),
  apiPost: vi.fn(),
}));

describe("clearing API", () => {
  beforeEach(() => {
    vi.mocked(apiGet).mockReset();
  });

  it("loads the compatibility batch review list as a flat array", async () => {
    vi.mocked(apiGet).mockResolvedValue([
      {
        id: "batch-1",
        merchant_id: "merchant-1",
        date_from: "2025-12-04",
        date_to: "2025-12-04",
        total_amount: 1200,
        status: "PENDING",
      },
    ]);

    const batches = await fetchClearingBatches({ date_from: "2025-12-04", date_to: "2025-12-04" });

    expect(apiGet).toHaveBeenCalledWith("/clearing/batches", {
      date_from: "2025-12-04",
      date_to: "2025-12-04",
    });
    expect(batches).toHaveLength(1);
    expect(batches[0].merchant_id).toBe("merchant-1");
  });

  it("maps detail payload into the page-friendly batch + operations shape", async () => {
    vi.mocked(apiGet).mockResolvedValue({
      id: "batch-2",
      merchant_id: "merchant-2",
      date_from: "2025-12-05",
      date_to: "2025-12-05",
      total_amount: 900,
      status: "SENT",
      operations: [{ id: "op-link-1", batch_id: "batch-2", operation_id: "op-1", amount: 900 }],
    });

    const detail = await fetchClearingBatchDetails("batch-2");

    expect(apiGet).toHaveBeenCalledWith("/clearing/batches/batch-2");
    expect(detail.batch.id).toBe("batch-2");
    expect(detail.operations).toEqual([{ id: "op-link-1", batch_id: "batch-2", operation_id: "op-1", amount: 900 }]);
  });
});

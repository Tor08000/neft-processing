import { describe, expect, it } from "vitest";
import { buildPayoutBatchesQuery } from "./payouts";

describe("buildPayoutBatchesQuery", () => {
  it("builds query params for payouts", () => {
    const query = buildPayoutBatchesQuery({
      tenant_id: "tenant-1",
      partner_id: "AZS-123",
      date_from: "2025-12-01",
      date_to: "2025-12-07",
      limit: 50,
      offset: 100,
      state: ["READY", "SENT"],
      sort: "created_at:desc",
    });

    expect(query).toEqual({
      tenant_id: "tenant-1",
      partner_id: "AZS-123",
      date_from: "2025-12-01",
      date_to: "2025-12-07",
      limit: 50,
      offset: 100,
      state: "READY,SENT",
      sort: "created_at:desc",
    });
  });
});

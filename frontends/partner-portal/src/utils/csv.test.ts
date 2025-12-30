import { describe, expect, it } from "vitest";
import { parseCsv } from "./csv";

describe("parseCsv", () => {
  it("parses valid csv rows", () => {
    const text = `station_code,product_code,price,currency,valid_from
AZS-001,FUEL-95,52.4,RUB,2024-02-01`;
    const result = parseCsv(text);
    expect(result.errors).toHaveLength(0);
    expect(result.rows).toHaveLength(1);
    expect(result.rows[0].station_code).toBe("AZS-001");
  });
});

import { describe, expect, it } from "vitest";
import { parseCatalogCsv, parseCsv } from "./csv";

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

describe("parseCatalogCsv", () => {
  it("returns error when required header is missing", () => {
    const text = `kind,title,uom
SERVICE,Мойка,услуга`;
    const result = parseCatalogCsv(text);
    expect(result.errors.length).toBeGreaterThan(0);
    expect(result.errors[0].message).toMatch(/колонку/);
  });

  it("parses catalog rows with valid headers", () => {
    const text = `kind,title,category,uom,description,status
SERVICE,Мойка,Автомойка,услуга,Полный комплекс,ACTIVE`;
    const result = parseCatalogCsv(text);
    expect(result.errors).toHaveLength(0);
    expect(result.rows).toHaveLength(1);
    expect(result.rows[0].title).toBe("Мойка");
  });
});

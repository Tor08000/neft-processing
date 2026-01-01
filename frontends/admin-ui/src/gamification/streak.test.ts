import { describe, expect, it } from "vitest";
import { updateStreak } from "./streak";

const BASE_DATE = new Date("2024-01-01T00:00:00Z");

describe("updateStreak", () => {
  it("increments within rolling window", () => {
    const previous = { count: 2, lastRunAt: "2024-01-01T00:00:00Z" };
    const next = updateStreak(previous, new Date("2024-01-01T12:00:00Z"));
    expect(next.count).toBe(3);
  });

  it("resets after window expires", () => {
    const previous = { count: 5, lastRunAt: "2024-01-01T00:00:00Z" };
    const next = updateStreak(previous, new Date("2024-01-03T01:00:00Z"));
    expect(next.count).toBe(1);
  });

  it("starts streak when no previous state", () => {
    const next = updateStreak(null, BASE_DATE);
    expect(next.count).toBe(1);
  });
});

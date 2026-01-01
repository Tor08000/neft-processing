import { describe, expect, it } from "vitest";
import { buildMasterySnapshot } from "./levels";
import { computeQualitySignals, deriveCountersFromEvents } from "./metrics";
import { compactMasteryEvents } from "./storage";
import type { MasteryEvent } from "./types";

const makeExplainEvent = (at: string, overrides?: Partial<MasteryEvent>): MasteryEvent => ({
  type: "explain_run_success",
  at,
  score: { level: "risky", confidence: 0.7, penalty: 0.5 },
  ...overrides,
});

const makeEvent = (type: MasteryEvent["type"], at: string, overrides?: Partial<MasteryEvent>): MasteryEvent => ({
  type,
  at,
  ...overrides,
});

describe("mastery progression", () => {
  it("promotes to Operator after first explain", () => {
    const events = [makeExplainEvent("2024-01-01T00:00:00Z")];
    const snapshot = buildMasterySnapshot({
      events,
      state: { version: 1, updatedAt: "2024-01-01T00:00:00Z", counters: deriveCountersFromEvents(events) },
      streakCount: 1,
    });

    expect(snapshot.level).toBe("operator");
    expect(snapshot.counters.totalExplains).toBe(1);
  });

  it("promotes to Senior Operator when gates met", () => {
    const events: MasteryEvent[] = [];
    for (let i = 0; i < 20; i += 1) {
      events.push(
        makeExplainEvent(`2024-01-01T00:${String(i).padStart(2, "0")}:00Z`, {
          score: { level: "risky", confidence: 0.65, penalty: 0.4 },
        }),
      );
    }
    for (let i = 0; i < 3; i += 1) {
      events.push(makeEvent("diff_run_success", `2024-01-01T01:${String(i).padStart(2, "0")}:00Z`));
    }
    for (let i = 0; i < 5; i += 1) {
      events.push(
        makeEvent("case_created", `2024-01-01T02:${String(i).padStart(2, "0")}:00Z`, {
          selected_actions_count: 1,
        }),
      );
    }

    const snapshot = buildMasterySnapshot({
      events,
      state: { version: 1, updatedAt: "2024-01-01T00:00:00Z", counters: deriveCountersFromEvents(events) },
      streakCount: 3,
    });

    expect(snapshot.level).toBe("senior_operator");
  });

  it("promotes to Risk Strategist when quality signals are strong", () => {
    const events: MasteryEvent[] = [];
    const base = new Date("2024-01-01T00:00:00Z");
    let cursor = base.getTime();

    for (let i = 0; i < 10; i += 1) {
      events.push(
        makeEvent("case_created", new Date(cursor).toISOString(), {
          selected_actions_count: 2,
          score: { level: "critical", confidence: 0.4, penalty: 0.9 },
        }),
      );
      cursor += 60 * 60 * 1000;
      const improved = i < 8;
      events.push(
        makeExplainEvent(new Date(cursor).toISOString(), {
          score: {
            level: improved ? "clean" : "risky",
            confidence: 0.7,
            penalty: improved ? 0.2 : 0.85,
          },
        }),
      );
      cursor += 60 * 60 * 1000;
    }

    for (let i = 0; i < 50; i += 1) {
      events.push(
        makeExplainEvent(new Date(cursor).toISOString(), {
          score: { level: "risky", confidence: 0.7, penalty: 0.5 },
        }),
      );
      cursor += 60 * 1000;
    }

    for (let i = 0; i < 10; i += 1) {
      events.push(makeEvent("diff_run_success", new Date(cursor + i * 1000).toISOString()));
    }

    for (let i = 0; i < 5; i += 1) {
      events.push(
        makeEvent("case_created", new Date(cursor + 60 * 1000 + i * 1000).toISOString(), {
          selected_actions_count: 1,
        }),
      );
    }

    const counters = deriveCountersFromEvents(events);
    counters.totalCasesCreated = 15;

    const signals = computeQualitySignals(events);
    expect(signals.improvements).toBeGreaterThanOrEqual(8);
    expect(signals.cleanAfterActionRate).toBeGreaterThanOrEqual(0.35);

    const snapshot = buildMasterySnapshot({
      events,
      state: { version: 1, updatedAt: "2024-01-01T00:00:00Z", counters },
      streakCount: 6,
    });

    expect(snapshot.level).toBe("risk_strategist");
  });
});

describe("mastery storage compaction", () => {
  it("trims events beyond 500 entries", () => {
    const events: MasteryEvent[] = [];
    for (let i = 0; i < 501; i += 1) {
      events.push(
        makeEvent("explain_run_success", new Date(2024, 0, 1, 0, i).toISOString(), {
          case_id: `case-${i}`,
        }),
      );
    }
    const compacted = compactMasteryEvents(events, new Date("2024-01-10T00:00:00Z"));
    expect(compacted).toHaveLength(500);
    expect(compacted.some((event) => event.case_id === "case-0")).toBe(false);
  });
});

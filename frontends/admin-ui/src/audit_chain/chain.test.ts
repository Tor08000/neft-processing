import { webcrypto } from "crypto";
import { describe, expect, test } from "vitest";
import type { CaseEvent } from "../api/adminCases";
import { canonicalStringify } from "./canonical";
import { computeChain, verifyChain } from "./chain";

if (!globalThis.crypto) {
  // @ts-expect-error - webcrypto matches browser Crypto
  globalThis.crypto = webcrypto;
}

const makeEvent = (overrides: Partial<CaseEvent>): CaseEvent => ({
  id: overrides.id ?? "evt",
  at: overrides.at ?? new Date("2024-01-01T00:00:00.000Z").toISOString(),
  type: overrides.type ?? "CASE_CREATED",
  actor: overrides.actor ?? { email: "agent@example.com" },
  meta: overrides.meta ?? null,
  request_id: overrides.request_id,
  trace_id: overrides.trace_id,
  source: overrides.source,
  prev_hash: overrides.prev_hash,
  hash: overrides.hash,
});

const makeEvents = (): CaseEvent[] => [
  makeEvent({
    id: "evt-1",
    at: "2024-01-01T00:00:00.000Z",
    type: "CASE_CREATED",
    meta: {
      changes: [{ field: "status", from: null, to: "OPEN" }],
      reason: "Case created",
    },
    source: "backend",
  }),
  makeEvent({
    id: "evt-2",
    at: "2024-01-02T00:00:00.000Z",
    type: "NOTE_UPDATED",
    meta: {
      changes: [{ field: "note", from: null, to: "Call client" }],
    },
    source: "backend",
  }),
  makeEvent({
    id: "evt-3",
    at: "2024-01-03T00:00:00.000Z",
    type: "STATUS_CHANGED",
    meta: {
      changes: [{ field: "status", from: "OPEN", to: "IN_PROGRESS" }],
    },
    source: "backend",
  }),
];

describe("canonicalStringify", () => {
  test("stable key order", () => {
    const a = canonicalStringify({ b: 1, a: 2 });
    const b = canonicalStringify({ a: 2, b: 1 });
    expect(a).toBe(b);
  });
});

describe("audit chain", () => {
  test("stable chain verifies", async () => {
    const events = makeEvents();
    const result = await verifyChain("case-1", events);
    expect(result.status).toBe("verified");
  });

  test("tamper detection", async () => {
    const events = makeEvents();
    const tampered = [...events];
    tampered[1] = makeEvent({
      ...tampered[1],
      meta: {
        changes: [{ field: "note", from: null, to: "Tampered" }],
      },
    });

    const links = await computeChain("case-1", events);
    const result = await verifyChain("case-1", tampered, links);
    expect(result.status).toBe("broken");
    expect(result.broken_at_index).toBe(1);
  });

  test("reorder detection", async () => {
    const events = makeEvents();
    const reordered = [events[1], events[0], events[2]];
    const links = await computeChain("case-1", events);
    const result = await verifyChain("case-1", reordered, links);
    expect(result.status).toBe("broken");
  });

  test("redaction stability", async () => {
    const events = [
      makeEvent({
        id: "evt-1",
        type: "NOTE_UPDATED",
        meta: {
          changes: [{ field: "user.email", from: null, to: "user@example.com" }],
        },
        source: "backend",
      }),
    ];
    const first = await computeChain("case-1", events);
    const second = await computeChain("case-1", events);
    expect(first[0]?.hash).toBe(second[0]?.hash);
  });
});

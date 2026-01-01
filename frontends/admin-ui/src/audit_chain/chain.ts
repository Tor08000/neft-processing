import type { CaseEvent } from "../api/adminCases";
import { isRedactedValue, redactForAudit } from "../redaction/apply";
import { canonicalStringify } from "./canonical";
import { sha256 } from "./hash";
import type { AuditPayload, ChainLink, ChainVerificationResult } from "./types";

const GENESIS_HASH = "GENESIS";
const CACHE_PREFIX = "neft_admin_audit_chain_v1:";

const getCacheKey = (caseId: string) => `${CACHE_PREFIX}${caseId}`;

const saveChainCache = (caseId: string, links: ChainLink[]) => {
  if (typeof localStorage === "undefined") return;
  try {
    localStorage.setItem(
      getCacheKey(caseId),
      JSON.stringify({
        computed_at: new Date().toISOString(),
        links,
      }),
    );
  } catch {
    // ignore cache failures
  }
};

const deriveSource = (event: CaseEvent): AuditPayload["source"] => {
  if (event.source) return event.source;
  if (event.id.startsWith("synthetic_")) return "synthetic";
  return "backend";
};

const normalizeActor = (actor?: CaseEvent["actor"] | null): AuditPayload["actor"] => {
  if (!actor) return null;
  const { id, email } = actor;
  if (!id && !email) return null;
  return { id: id ?? undefined, email: email ?? undefined };
};

const redactForChain = (field: string, value: unknown) => {
  const redacted = redactForAudit(field, value);
  if (isRedactedValue(redacted)) {
    const { hash: _hash, ...rest } = redacted;
    return rest;
  }
  return redacted;
};

const buildAuditPayload = (caseId: string, event: CaseEvent): AuditPayload => {
  const changes = event.meta?.changes?.map((change) => ({
    field: change.field,
    from: redactForChain(change.field, change.from),
    to: redactForChain(change.field, change.to),
  }));

  const artifact = event.meta?.export_ref
    ? {
        kind: event.meta.export_ref.kind,
        id: event.meta.export_ref.id,
        url: event.meta.export_ref.url ?? null,
      }
    : null;

  const payload: AuditPayload = {
    id: event.id,
    case_id: caseId,
    at: event.at,
    type: event.type,
    actor: normalizeActor(event.actor),
    source: deriveSource(event),
  };

  if (event.request_id !== undefined) {
    payload.request_id = event.request_id ?? null;
  }
  if (event.trace_id !== undefined) {
    payload.trace_id = event.trace_id ?? null;
  }
  if (changes && changes.length > 0) {
    payload.changes = changes;
  }
  if (artifact) {
    payload.artifact = artifact;
  }
  if (event.meta?.reason !== undefined) {
    payload.reason = event.meta?.reason ?? null;
  }

  return payload;
};

const buildChainLink = async (prevHash: string, payload: AuditPayload) => {
  const material = `${prevHash}\n${canonicalStringify(payload)}`;
  return sha256(material);
};

const canUseBackendLinks = (events: CaseEvent[]) =>
  events.length > 0 &&
  events.every(
    (event) =>
      typeof event.hash === "string" && event.hash.length > 0 && typeof event.prev_hash === "string",
  );

const extractBackendLinks = (events: CaseEvent[]): ChainLink[] =>
  events.map((event) => ({
    event_id: event.id,
    prev_hash: event.prev_hash ?? "",
    hash: event.hash ?? "",
  }));

export const computeChain = async (caseId: string, events: CaseEvent[]): Promise<ChainLink[]> => {
  if (!caseId || events.length === 0) return [];
  let prevHash = GENESIS_HASH;
  const links: ChainLink[] = [];
  for (const event of events) {
    const payload = buildAuditPayload(caseId, event);
    const hash = await buildChainLink(prevHash, payload);
    links.push({ event_id: event.id, prev_hash: prevHash, hash });
    prevHash = hash;
  }
  saveChainCache(caseId, links);
  return links;
};

export const verifyChain = async (
  caseId: string,
  events: CaseEvent[],
  links?: ChainLink[],
): Promise<ChainVerificationResult> => {
  if (!caseId || events.length === 0) {
    return { status: "unknown" };
  }

  const expectedLinks = await computeChain(caseId, events);
  const providedLinks = links && links.length === events.length ? links : null;

  if (expectedLinks.length === 0) {
    return { status: "unknown" };
  }

  if (canUseBackendLinks(events) || providedLinks) {
    const actualLinks = canUseBackendLinks(events) ? extractBackendLinks(events) : providedLinks ?? [];
    for (let i = 0; i < expectedLinks.length; i += 1) {
      const expected = expectedLinks[i];
      const actual = actualLinks[i];
      if (expected.hash !== actual.hash || expected.prev_hash !== actual.prev_hash) {
        return {
          status: "broken",
          broken_at_index: i,
          expected_hash: expected.hash,
          actual_hash: actual.hash,
        };
      }
    }
    return { status: "verified" };
  }

  return { status: "verified" };
};

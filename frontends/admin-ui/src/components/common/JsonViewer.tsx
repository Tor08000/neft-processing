import React, { useMemo, useState } from "react";
import { CopyButton } from "../CopyButton/CopyButton";
import { isRedactedValue, redactObjectDeep } from "../../redaction/apply";
import type { RedactedValue } from "../../redaction/types";

interface JsonViewerProps {
  value: unknown;
  title?: string;
  enableSearch?: boolean;
  enableCollapse?: boolean;
  collapsedLines?: number;
  redactionMode?: "off" | "audit" | "viewer" | "export";
}

const TOKEN_PREFIX = "__REDACTED_TOKEN_";
const TOKEN_REGEX = new RegExp(`${TOKEN_PREFIX}\\d+__`, "g");

const serializeWithRedaction = (value: unknown) => {
  const tokenMap = new Map<string, RedactedValue>();
  let tokenIndex = 0;
  if (typeof value === "string") {
    const formatted = value;
    const formattedWithTokens = formatted;
    return { formatted, formattedWithTokens, tokenMap };
  }
  if (isRedactedValue(value)) {
    const token = `${TOKEN_PREFIX}${tokenIndex}__`;
    tokenIndex += 1;
    tokenMap.set(token, value);
    const formattedWithTokens = token;
    const formatted = `REDACTED: ${value.display}`;
    return { formatted, formattedWithTokens, tokenMap };
  }
  const replacer = (_key: string, val: unknown) => {
    if (isRedactedValue(val)) {
      const token = `${TOKEN_PREFIX}${tokenIndex}__`;
      tokenIndex += 1;
      tokenMap.set(token, val);
      return token;
    }
    return val;
  };
  const formattedWithTokens = JSON.stringify(value ?? {}, replacer, 2);
  const formatted = formattedWithTokens.replace(TOKEN_REGEX, (token) => {
    const redacted = tokenMap.get(token);
    if (!redacted) return token;
    return `REDACTED: ${redacted.display}`;
  });
  return { formatted, formattedWithTokens, tokenMap };
};

const renderLineWithRedactions = (line: string, tokenMap: Map<string, RedactedValue>) => {
  const parts: React.ReactNode[] = [];
  let lastIndex = 0;
  let match: RegExpExecArray | null;
  const regex = new RegExp(TOKEN_REGEX.source, "g");
  while ((match = regex.exec(line)) !== null) {
    const [fullMatch, token] = match;
    if (match.index > lastIndex) {
      parts.push(line.slice(lastIndex, match.index));
    }
    const redacted = tokenMap.get(token);
    if (redacted) {
      const tooltip = `${redacted.reason.message} (${redacted.reason.kind}:${redacted.reason.rule})`;
      parts.push(
        <span key={`${token}-${match.index}`} className="json-viewer__redacted" title={tooltip}>
          {`"REDACTED: ${redacted.display}"`}
        </span>,
      );
    } else {
      parts.push(fullMatch);
    }
    lastIndex = match.index + fullMatch.length;
  }
  if (lastIndex < line.length) {
    parts.push(line.slice(lastIndex));
  }
  return parts;
};

export const JsonViewer: React.FC<JsonViewerProps> = ({
  value,
  title,
  enableSearch = false,
  enableCollapse = false,
  collapsedLines = 20,
  redactionMode = "viewer",
}) => {
  const [query, setQuery] = useState("");
  const [collapsed, setCollapsed] = useState(false);

  const formattedPayload = useMemo(() => {
    let resolved: unknown = value;
    if (typeof value === "string") {
      try {
        resolved = JSON.parse(value);
      } catch {
        resolved = value;
      }
    }
    const redacted = redactionMode === "off" ? resolved : redactObjectDeep(resolved, { mode: redactionMode });
    return serializeWithRedaction(redacted);
  }, [redactionMode, value]);

  const linesWithTokens = useMemo(() => formattedPayload.formattedWithTokens.split("\n"), [formattedPayload]);
  const lines = useMemo(() => formattedPayload.formatted.split("\n"), [formattedPayload]);
  const filteredIndexes = useMemo(() => {
    if (!query) return lines.map((_line, index) => index);
    const lowered = query.toLowerCase();
    return lines.reduce<number[]>((acc, line, index) => {
      if (line.toLowerCase().includes(lowered)) acc.push(index);
      return acc;
    }, []);
  }, [lines, query]);

  const visibleIndexes = useMemo(() => {
    if (!enableCollapse || !collapsed || filteredIndexes.length <= collapsedLines) {
      return filteredIndexes;
    }
    return [...filteredIndexes.slice(0, collapsedLines), -1];
  }, [collapsed, collapsedLines, enableCollapse, filteredIndexes]);

  return (
    <div className="json-viewer">
      <div className="json-viewer__header">
        <strong>{title ?? "JSON"}</strong>
        <div className="json-viewer__actions">
          {enableSearch ? (
            <input
              type="search"
              value={query}
              onChange={(event) => setQuery(event.target.value)}
              placeholder="Search"
            />
          ) : null}
          {enableCollapse && filteredIndexes.length > collapsedLines ? (
            <button type="button" className="ghost" onClick={() => setCollapsed((prev) => !prev)}>
              {collapsed ? "Expand" : "Collapse"}
            </button>
          ) : null}
          <CopyButton value={formattedPayload.formatted} label="Copy JSON" />
        </div>
      </div>
      {enableSearch && query ? (
        <div className="json-viewer__meta">{filteredIndexes.length} lines match</div>
      ) : null}
      <pre className="json-viewer__content">
        {visibleIndexes.map((lineIndex, index) => {
          if (lineIndex === -1) return <div key={`ellipsis-${index}`}>…</div>;
          const line = linesWithTokens[lineIndex];
          return (
            <div key={`line-${lineIndex}`}>
              {renderLineWithRedactions(line, formattedPayload.tokenMap)}
            </div>
          );
        })}
      </pre>
    </div>
  );
};

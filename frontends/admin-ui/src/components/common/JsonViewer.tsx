import React, { useMemo, useState } from "react";
import { CopyButton } from "../CopyButton/CopyButton";

interface JsonViewerProps {
  value: unknown;
  title?: string;
  enableSearch?: boolean;
  enableCollapse?: boolean;
  collapsedLines?: number;
}

export const JsonViewer: React.FC<JsonViewerProps> = ({
  value,
  title,
  enableSearch = false,
  enableCollapse = false,
  collapsedLines = 20,
}) => {
  const [query, setQuery] = useState("");
  const [collapsed, setCollapsed] = useState(false);

  const formatted = useMemo(() => {
    if (typeof value === "string") {
      try {
        return JSON.stringify(JSON.parse(value), null, 2);
      } catch {
        return value;
      }
    }
    return JSON.stringify(value ?? {}, null, 2);
  }, [value]);

  const lines = useMemo(() => formatted.split("\n"), [formatted]);
  const filteredLines = useMemo(() => {
    if (!query) return lines;
    const lowered = query.toLowerCase();
    return lines.filter((line) => line.toLowerCase().includes(lowered));
  }, [lines, query]);

  const visibleLines = useMemo(() => {
    if (!enableCollapse || !collapsed || filteredLines.length <= collapsedLines) {
      return filteredLines;
    }
    return [...filteredLines.slice(0, collapsedLines), "…"];
  }, [collapsed, collapsedLines, enableCollapse, filteredLines]);

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
          {enableCollapse && filteredLines.length > collapsedLines ? (
            <button type="button" className="ghost" onClick={() => setCollapsed((prev) => !prev)}>
              {collapsed ? "Expand" : "Collapse"}
            </button>
          ) : null}
          <CopyButton value={formatted} label="Copy JSON" />
        </div>
      </div>
      {enableSearch && query ? (
        <div className="json-viewer__meta">{filteredLines.length} lines match</div>
      ) : null}
      <pre className="json-viewer__content">{visibleLines.join("\n")}</pre>
    </div>
  );
};

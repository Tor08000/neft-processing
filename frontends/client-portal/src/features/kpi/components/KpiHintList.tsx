import type { KpiHint } from "../types";

interface KpiHintListProps {
  hints: KpiHint[];
}

export const KpiHintList = ({ hints }: KpiHintListProps) => (
  <ul className="kpi-hints">
    {hints.map((hint) => (
      <li key={hint.id} className={hint.tone ? `kpi-hints__item is-${hint.tone}` : "kpi-hints__item"}>
        <span className="kpi-hints__icon" aria-hidden>
          {hint.icon ?? "•"}
        </span>
        <span>{hint.label}</span>
      </li>
    ))}
  </ul>
);

export default KpiHintList;

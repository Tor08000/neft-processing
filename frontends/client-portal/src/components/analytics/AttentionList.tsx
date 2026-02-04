import { Link } from "react-router-dom";
import type { AnalyticsAttentionItem } from "../../types/analytics";

interface AttentionListProps {
  items: AnalyticsAttentionItem[];
}

const isExternalLink = (href: string) => href.startsWith("http://") || href.startsWith("https://");

export function AttentionList({ items }: AttentionListProps) {
  if (!items.length) {
    return null;
  }

  return (
    <ul className="attention-list">
      {items.map((item) => {
        const content = (
          <>
            <div className="attention-list__title">{item.title}</div>
            {item.description ? <div className="muted small">{item.description}</div> : null}
          </>
        );
        return (
          <li key={item.id} className={`attention-list__item attention-list__item--${item.severity ?? "info"}`}>
            {isExternalLink(item.href) ? (
              <a href={item.href} target="_blank" rel="noreferrer">
                {content}
              </a>
            ) : (
              <Link to={item.href}>{content}</Link>
            )}
          </li>
        );
      })}
    </ul>
  );
}

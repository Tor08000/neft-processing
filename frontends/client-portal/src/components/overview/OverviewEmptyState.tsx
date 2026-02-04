type OverviewEmptyStateProps = {
  title: string;
  description: string;
  actionLabel: string;
  onAction: () => void;
};

export function OverviewEmptyState({ title, description, actionLabel, onAction }: OverviewEmptyStateProps) {
  return (
    <div className="neftc-empty-state">
      <div>
        <div className="neftc-empty-state__title">{title}</div>
        <div className="neftc-empty-state__description neftc-text-muted">{description}</div>
      </div>
      <button type="button" className="neftc-btn-secondary" onClick={onAction}>
        {actionLabel}
      </button>
    </div>
  );
}

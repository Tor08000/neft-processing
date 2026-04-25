import { useState } from "react";
import { Link } from "react-router-dom";
import { SupportRequestModal } from "./SupportRequestModal";
import type { SupportRequestSubjectType } from "../types/support";

type RelatedLink = {
  to: string;
  label: string;
};

type PartnerSupportActionsProps = {
  title: string;
  description: string;
  requestTitle: string;
  subjectType?: SupportRequestSubjectType;
  subjectId?: string | null;
  relatedLinks?: RelatedLink[];
};

export function PartnerSupportActions({
  title,
  description,
  requestTitle,
  subjectType = "OTHER",
  subjectId,
  relatedLinks = [],
}: PartnerSupportActionsProps) {
  const [isOpen, setIsOpen] = useState(false);

  return (
    <>
      <section className="card">
        <div className="card__header">
          <div>
            <h3>{title}</h3>
            <p className="muted">{description}</p>
          </div>
        </div>
        {relatedLinks.length ? (
          <div className="actions" style={{ marginBottom: 12 }}>
            {relatedLinks.map((link) => (
              <Link key={`${link.to}-${link.label}`} className="ghost" to={link.to}>
                {link.label}
              </Link>
            ))}
          </div>
        ) : null}
        <div className="actions">
          <Link className="ghost" to="/support/requests">
            Открыть обращения
          </Link>
          <button type="button" className="primary" onClick={() => setIsOpen(true)}>
            Создать обращение
          </button>
        </div>
      </section>
      <SupportRequestModal
        isOpen={isOpen}
        onClose={() => setIsOpen(false)}
        subjectType={subjectType}
        subjectId={subjectId}
        defaultTitle={requestTitle}
      />
    </>
  );
}

import { FormEvent, ReactNode, useMemo, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { createOrg } from "../api/clientPortal";
import { useAuth } from "../auth/AuthContext";
import { useClient } from "../auth/ClientContext";
import { useClientJourney } from "../auth/ClientJourneyContext";
import type { DocumentStatus } from "../auth/clientJourney";
import { CustomerType, getPlanByCode, getPlansByAudience } from "@shared/subscriptions/catalog";

export type ConnectProfileField = "fullName" | "legalName" | "phone" | "email" | "inn" | "kpp" | "ogrn" | "ogrnip" | "address" | "contact";
type ConnectProfileValues = Record<ConnectProfileField, string>;
type ConnectProfileErrors = Partial<Record<ConnectProfileField, string>>;
type ConnectStepKey = "plan" | "type" | "profile" | "documents" | "sign" | "payment";
type ConnectDocument = { code: string; name: string; required: boolean };

const CLIENT_PLANS = getPlansByAudience("CLIENT");
const CONNECT_STEPS: Array<{ key: ConnectStepKey; label: string }> = [
  { key: "plan", label: "Tariff" },
  { key: "type", label: "Client type" },
  { key: "profile", label: "Profile" },
  { key: "documents", label: "Documents" },
  { key: "sign", label: "Signature" },
  { key: "payment", label: "Payment" },
];

const TYPE_DETAILS: Array<{ code: CustomerType; label: string; description: string; requirements: string }> = [
  { code: "INDIVIDUAL", label: "Individual", description: "For personal use with minimal company details.", requirements: "You will need personal contacts and address." },
  { code: "SOLE_PROPRIETOR", label: "Sole Proprietor", description: "For individual entrepreneurs registered as sole proprietors.", requirements: "Prepare INN and OGRNIP to continue." },
  { code: "LEGAL_ENTITY", label: "Legal Entity", description: "For LLC/JSC and other corporate entities.", requirements: "Prepare legal company identifiers and legal address." },
];

const PROFILE_FIELD_LABELS: Record<ConnectProfileField, string> = {
  fullName: "Full name",
  legalName: "Legal company name",
  phone: "Phone",
  email: "Email",
  inn: "INN",
  kpp: "KPP",
  ogrn: "OGRN",
  ogrnip: "OGRNIP",
  address: "Address",
  contact: "Contact person",
};

const DOCUMENT_STATUS_LABELS: Record<DocumentStatus, string> = {
  pending_generation: "pending_generation",
  ready: "ready",
  reviewed: "reviewed",
};

function ConnectStepShell({ step, title, description, children, aside }: { step: ConnectStepKey; title: string; description: string; children: ReactNode; aside?: ReactNode }) {
  const stepIndex = CONNECT_STEPS.findIndex((item) => item.key === step);
  return (
    <section className="stack card neft-card" data-testid={`connect-step-${step}`}>
      <div className="stack" style={{ gap: 8 }}>
        <h1>{title}</h1>
        <p className="muted">{description}</p>
        <div className="muted" aria-label="wizard-progress">Step {stepIndex + 1} of {CONNECT_STEPS.length}: {CONNECT_STEPS[stepIndex]?.label}</div>
        <ol style={{ display: "grid", gridTemplateColumns: "repeat(3, minmax(0,1fr))", gap: 8, paddingLeft: 20, margin: 0 }}>
          {CONNECT_STEPS.map((item, index) => (
            <li key={item.key} style={{ fontWeight: item.key === step ? 700 : 400, opacity: index <= stepIndex ? 1 : 0.65 }}>{item.label}</li>
          ))}
        </ol>
      </div>
      {aside}
      {children}
    </section>
  );
}

function ConnectSummaryCard() {
  const { draft, state, nextRoute } = useClientJourney();
  const plan = getPlanByCode(draft.selectedPlan);
  const companyName = draft.profileData?.legalName ?? draft.profileData?.fullName ?? "Not entered";
  return (
    <div className="card neft-card" style={{ marginTop: 8 }}>
      <strong>Connection summary</strong>
      <div className="muted">Current stage: {state}</div>
      <div className="muted">Next step: {nextRoute}</div>
      <div>Plan: {plan?.title ?? "Not selected"}</div>
      <div>Customer type: {draft.customerType ?? "Not selected"}</div>
      <div>Company/client name: {companyName}</div>
    </div>
  );
}

const getDocumentList = (customerType?: CustomerType | null): ConnectDocument[] => {
  const base: ConnectDocument[] = [
    { code: "service_agreement", name: "Service agreement", required: true },
    { code: "onboarding_ack", name: "Onboarding documents acknowledgement", required: true },
  ];
  if (customerType === "LEGAL_ENTITY") {
    base.push({ code: "corporate_requisites", name: "Corporate requisites appendix", required: true });
  }
  if (customerType === "SOLE_PROPRIETOR") {
    base.push({ code: "ip_tax_notice", name: "Sole proprietor tax notice", required: true });
  }
  if (customerType === "INDIVIDUAL") {
    base.push({ code: "personal_data_consent", name: "Personal data consent", required: true });
  }
  return base;
};

const getDocumentStatusMap = (
  docs: ConnectDocument[],
  docsByCode: Record<string, DocumentStatus> | undefined,
  docsGenerated: boolean | undefined,
  docsViewed: boolean | undefined,
): Record<string, DocumentStatus> => {
  if (docsByCode) {
    return docs.reduce<Record<string, DocumentStatus>>((acc, doc) => {
      acc[doc.code] = docsByCode[doc.code] ?? "pending_generation";
      return acc;
    }, {});
  }

  return docs.reduce<Record<string, DocumentStatus>>((acc, doc) => {
    if (!docsGenerated) {
      acc[doc.code] = "pending_generation";
    } else if (docsViewed) {
      acc[doc.code] = "reviewed";
    } else {
      acc[doc.code] = "ready";
    }
    return acc;
  }, {});
};

export function ConnectHomePage() {
  const { state, nextRoute } = useClientJourney();
  return (
    <ConnectStepShell step="plan" title="Finish your company connection" description="Continue the onboarding wizard to unlock the full client cabinet and billing features." aside={<ConnectSummaryCard />}>
      <p>Current stage: {state}</p>
      <Link className="neft-button neft-btn-primary" to={nextRoute === "/connect" ? "/connect/plan" : nextRoute}>Continue setup</Link>
    </ConnectStepShell>
  );
}

export function ConnectPlanPage() {
  const { updateDraft, draft } = useClientJourney();
  const navigate = useNavigate();

  return (
    <ConnectStepShell step="plan" title="Choose your tariff" description="Select the plan that best matches your expected usage. You can change it before payment." aside={<ConnectSummaryCard />}>
      <div className="stack">
        {CLIENT_PLANS.map((plan) => {
          const isSelected = draft.selectedPlan === plan.code;
          return (
            <article key={plan.code} className="card neft-card stack" data-testid={`plan-card-${plan.code}`} style={{ borderColor: isSelected ? "#2e7d32" : undefined }}>
              <h2>{plan.title} {plan.badge ? <span className="muted">· {plan.badge}</span> : null}</h2>
              <div>{plan.monthlyPrice == null ? "Contact sales" : `₽${plan.monthlyPrice} / month`}</div>
              <div className="muted">{plan.yearlyPrice == null ? plan.yearlyDiscountText ?? "Custom yearly terms" : `₽${plan.yearlyPrice} yearly (${plan.yearlyDiscountText ?? "discount"})`}</div>
              <p>{plan.description}</p>
              <ul>{plan.bullets.map((item) => <li key={item}>{item}</li>)}</ul>
              <div className="muted">Limits: users {plan.limits.users ?? "∞"}, cards {plan.limits.cards ?? "—"}, documents {plan.limits.documentsPerMonth ?? "—"}/mo</div>
              {plan.isTrial ? <div className="muted">Trial access is limited until subscription activation.</div> : null}
              {plan.isEnterprise ? <div className="muted">Enterprise includes custom contract terms and dedicated support.</div> : null}
              <button
                className={`neft-button ${isSelected ? "neft-btn-secondary" : "neft-btn-primary"}`}
                onClick={() => {
                  updateDraft({ selectedPlan: plan.code, subscriptionState: plan.isTrial ? "TRIAL_PENDING" : "NONE" });
                  navigate("/connect/type");
                }}
              >
                {isSelected ? "Selected" : `Choose plan: ${plan.shortTitle}`}
              </button>
            </article>
          );
        })}
      </div>
    </ConnectStepShell>
  );
}

export function ConnectTypePage() {
  const { updateDraft, draft } = useClientJourney();
  const navigate = useNavigate();

  return (
    <ConnectStepShell step="type" title="Choose client type" description="This choice defines required profile fields and onboarding documents." aside={<ConnectSummaryCard />}>
      <div className="stack">
        {TYPE_DETAILS.map((type) => (
          <article key={type.code} className="card neft-card stack" data-testid={`type-option-${type.code}`} style={{ borderColor: draft.customerType === type.code ? "#2e7d32" : undefined }}>
            <h2>{type.label}</h2>
            <p>{type.description}</p>
            <p className="muted">{type.requirements}</p>
            <button className="neft-button neft-btn-secondary" onClick={() => {
              updateDraft({ customerType: type.code, profileCompleted: false });
              navigate("/connect/profile");
            }}>Continue as {type.label}</button>
          </article>
        ))}
      </div>
    </ConnectStepShell>
  );
}

export function getProfileFields(customerType: CustomerType | null | undefined): ConnectProfileField[] {
  if (customerType === "INDIVIDUAL") return ["fullName", "phone", "email", "address"];
  if (customerType === "SOLE_PROPRIETOR") return ["fullName", "inn", "ogrnip", "address", "contact"];
  return ["legalName", "inn", "kpp", "ogrn", "address", "contact"];
}

export function ConnectProfilePage() {
  const { user } = useAuth();
  const { draft, updateDraft } = useClientJourney();
  const { refresh } = useClient();
  const navigate = useNavigate();
  const [values, setValues] = useState<ConnectProfileValues>({
    fullName: draft.profileData?.fullName ?? "",
    legalName: draft.profileData?.legalName ?? "",
    phone: draft.profileData?.phone ?? "",
    email: draft.profileData?.email ?? user?.email ?? "",
    address: draft.profileData?.address ?? "",
    inn: draft.profileData?.inn ?? "",
    kpp: draft.profileData?.kpp ?? "",
    ogrn: draft.profileData?.ogrn ?? "",
    ogrnip: draft.profileData?.ogrnip ?? "",
    contact: draft.profileData?.contact ?? "",
  });
  const [errors, setErrors] = useState<ConnectProfileErrors>({});
  const [submitError, setSubmitError] = useState<string | null>(null);
  const requiredFields = useMemo(() => getProfileFields(draft.customerType), [draft.customerType]);

  const setField = (field: ConnectProfileField, value: string) => {
    setValues((prev) => ({ ...prev, [field]: value }));
    setErrors((prev) => ({ ...prev, [field]: "" }));
    updateDraft({ profileData: { ...draft.profileData, [field]: value } });
  };

  const validate = () => {
    const nextErrors: ConnectProfileErrors = {};
    requiredFields.forEach((field) => {
      if (!values[field]?.trim()) {
        nextErrors[field] = "This field is required";
      }
    });
    setErrors(nextErrors);
    return Object.keys(nextErrors).length === 0;
  };

  const onSubmit = async (event: FormEvent) => {
    event.preventDefault();
    setSubmitError(null);
    if (!validate()) return;
    if (!draft.customerType) {
      setSubmitError("Choose client type first");
      return;
    }

    try {
      if (user) {
        const orgType = draft.customerType === "LEGAL_ENTITY" ? "LEGAL" : draft.customerType === "SOLE_PROPRIETOR" ? "IP" : "INDIVIDUAL";
        const name = draft.customerType === "LEGAL_ENTITY" ? values.legalName : values.fullName;
        await createOrg(user, { org_type: orgType, name, inn: values.inn || "-", kpp: values.kpp || null, ogrn: values.ogrn || values.ogrnip || null, address: values.address || null });
        await refresh();
      }
      updateDraft({ profileData: values, profileCompleted: true, documentsGenerated: false, documentsViewed: false, documentsByCode: undefined, signAccepted: false, documentsSigned: false, signatureState: "signPending", signAcceptedAt: undefined, subscriptionState: draft.selectedPlan === "CLIENT_FREE_TRIAL" ? "TRIAL_PENDING" : "PAYMENT_PENDING" });
      navigate("/connect/documents");
    } catch {
      setSubmitError("Unable to save profile. Check highlighted fields and try again.");
    }
  };

  if (!draft.customerType) {
    return (
      <ConnectStepShell step="profile" title="Profile details" description="Select client type before filling company details." aside={<ConnectSummaryCard />}>
        <Link to="/connect/type" className="neft-button neft-btn-primary">Go to client type</Link>
      </ConnectStepShell>
    );
  }

  return (
    <ConnectStepShell step="profile" title={draft.customerType === "LEGAL_ENTITY" ? "Company details" : "Personal details"} description="Fill only required fields for your selected client type." aside={<ConnectSummaryCard />}>
      <form onSubmit={onSubmit} className="stack">
        {submitError ? <div role="alert">{submitError}</div> : null}
        {requiredFields.map((field) => (
          <label key={field} className="stack" style={{ gap: 4 }}>
            <span>{PROFILE_FIELD_LABELS[field]} *</span>
            <input className="neft-input" value={values[field]} onChange={(event) => setField(field, event.target.value)} placeholder={PROFILE_FIELD_LABELS[field]} aria-invalid={Boolean(errors[field])} />
            {errors[field] ? <span role="alert" className="muted">{errors[field]}</span> : null}
          </label>
        ))}
        <div style={{ display: "flex", gap: 8 }}>
          <Link to="/connect/type" className="neft-button neft-btn-secondary">Back</Link>
          <button type="submit" className="neft-button neft-btn-primary">Continue</button>
        </div>
      </form>
    </ConnectStepShell>
  );
}

export function ConnectDocumentsPage() {
  const { draft, updateDraft, state } = useClientJourney();
  const navigate = useNavigate();
  const plan = getPlanByCode(draft.selectedPlan);
  const documents = useMemo(() => getDocumentList(draft.customerType), [draft.customerType]);
  const statusByDoc = useMemo(() => getDocumentStatusMap(documents, draft.documentsByCode, draft.documentsGenerated, draft.documentsViewed), [documents, draft.documentsByCode, draft.documentsGenerated, draft.documentsViewed]);
  const requiredReviewed = documents.filter((doc) => doc.required).every((doc) => statusByDoc[doc.code] === "reviewed");

  const updateDocumentStatus = (code: string, status: DocumentStatus) => {
    const nextStatuses = { ...statusByDoc, [code]: status };
    const allReviewed = documents.filter((doc) => doc.required).every((doc) => nextStatuses[doc.code] === "reviewed");
    updateDraft({ documentsByCode: nextStatuses, documentsGenerated: true, documentsViewed: allReviewed });
  };

  return (
    <ConnectStepShell step="documents" title="Review onboarding documents" description="Document generation is currently stubbed, but every action below updates explicit deterministic state." aside={<ConnectSummaryCard />}>
      <div className="card neft-card stack" style={{ gap: 4 }}>
        <strong>Step context</strong>
        <div>Selected plan: {plan?.title ?? draft.selectedPlan ?? "Not selected"}</div>
        <div>Customer type: {draft.customerType ?? "Not selected"}</div>
        <div>Client/company: {draft.profileData?.legalName ?? draft.profileData?.fullName ?? "Not entered"}</div>
        <div>Current connection stage: {state}</div>
      </div>

      <ul className="stack" style={{ listStyle: "none", paddingLeft: 0 }}>
        {documents.map((doc) => (
          <li key={doc.code} className="card neft-card stack" data-testid={`document-${doc.code}`}>
            <div style={{ display: "flex", justifyContent: "space-between", gap: 8 }}>
              <strong>{doc.name}</strong>
              <span className="muted">{DOCUMENT_STATUS_LABELS[statusByDoc[doc.code]]}</span>
            </div>
            <div style={{ display: "flex", gap: 8, flexWrap: "wrap" }}>
              <button className="neft-button neft-btn-secondary" type="button" onClick={() => updateDocumentStatus(doc.code, "ready")}>View</button>
              <button className="neft-button neft-btn-secondary" type="button" onClick={() => updateDocumentStatus(doc.code, "ready")}>Download</button>
              <button className="neft-button neft-btn-primary" type="button" onClick={() => updateDocumentStatus(doc.code, "reviewed")}>Mark as reviewed</button>
            </div>
          </li>
        ))}
      </ul>

      <div className="muted">All required documents must be reviewed before signing.</div>
      <button className="neft-button neft-btn-primary" disabled={!requiredReviewed} onClick={() => {
        updateDraft({ documentsGenerated: true, documentsViewed: true });
        navigate("/connect/sign");
      }}>Continue to signature</button>
    </ConnectStepShell>
  );
}

export function ConnectSignPage() {
  const { draft, updateDraft } = useClientJourney();
  const navigate = useNavigate();
  const plan = getPlanByCode(draft.selectedPlan);
  const [acceptDocs, setAcceptDocs] = useState(Boolean(draft.signAccepted));
  const [acceptProceed, setAcceptProceed] = useState(Boolean(draft.signatureState === "signAccepted"));
  const canProceed = acceptDocs && acceptProceed;

  return (
    <ConnectStepShell step="sign" title="Confirm and sign documents" description="Signing is stubbed in v1 (no digital signature provider yet), but acceptance is explicit and required." aside={<ConnectSummaryCard />}>
      <p>Subscription: {plan?.title ?? draft.selectedPlan ?? "Not selected"}</p>
      <ul>
        <li>Terms and conditions</li>
        <li>Plan agreement</li>
        <li>Onboarding documents acknowledgement</li>
      </ul>
      <label style={{ display: "flex", gap: 8 }}>
        <input type="checkbox" checked={acceptDocs} onChange={(event) => setAcceptDocs(event.target.checked)} />
        <span>I have reviewed and accept the documents.</span>
      </label>
      <label style={{ display: "flex", gap: 8 }}>
        <input type="checkbox" checked={acceptProceed} onChange={(event) => setAcceptProceed(event.target.checked)} />
        <span>I agree to proceed.</span>
      </label>
      <button className="neft-button neft-btn-primary" disabled={!canProceed} onClick={() => {
        const nextState = draft.selectedPlan === "CLIENT_FREE_TRIAL" ? "TRIAL_ACTIVE" : "PAYMENT_PENDING";
        updateDraft({ signAccepted: true, documentsSigned: true, signatureState: "signAccepted", signAcceptedAt: new Date().toISOString(), subscriptionState: nextState });
        navigate(draft.selectedPlan === "CLIENT_FREE_TRIAL" ? "/dashboard" : "/connect/payment");
      }}>Sign and continue</button>
    </ConnectStepShell>
  );
}

export function ConnectPaymentPage() {
  const { draft, updateDraft } = useClientJourney();
  const navigate = useNavigate();
  const plan = getPlanByCode(draft.selectedPlan);

  const paymentState = draft.subscriptionState === "PAYMENT_PROCESSING" || draft.subscriptionState === "PAYMENT_FAILED"
    ? draft.subscriptionState
    : "PAYMENT_PENDING";

  const isFreeTrial = draft.selectedPlan === "CLIENT_FREE_TRIAL";
  if (isFreeTrial) {
    return (
      <ConnectStepShell step="payment" title="Payment is skipped for free trial" description="Free trial activation does not require payment in v1." aside={<ConnectSummaryCard />}>
        <button className="neft-button neft-btn-primary" onClick={() => {
          updateDraft({ subscriptionState: "TRIAL_ACTIVE" });
          navigate("/dashboard");
        }}>Go to trial cabinet</button>
      </ConnectStepShell>
    );
  }

  return (
    <ConnectStepShell step="payment" title="Subscription payment" description="Payment provider integration is stubbed. Use simulation controls to complete deterministic state transitions." aside={<ConnectSummaryCard />}>
      <p>Selected plan: {plan?.title ?? draft.selectedPlan ?? "Not selected"}</p>
      <p>Billing period: Monthly</p>
      <p>Final amount: {plan?.monthlyPrice == null ? "Custom contract amount" : `₽${plan.monthlyPrice}`}</p>
      <p>Discount: {plan?.yearlyDiscountText ?? "No discount for monthly mode"}</p>
      <p>State: <strong>{paymentState}</strong></p>
      <div style={{ display: "flex", gap: 8, flexWrap: "wrap" }}>
        <button className="neft-button neft-btn-secondary" onClick={() => updateDraft({ subscriptionState: "PAYMENT_PROCESSING" })}>Proceed to payment</button>
        <button className="neft-button neft-btn-secondary" onClick={() => updateDraft({ subscriptionState: "PAYMENT_FAILED" })}>Simulate payment failure</button>
        <button className="neft-button neft-btn-primary" onClick={() => {
          updateDraft({ subscriptionState: "ACTIVE" });
          navigate("/dashboard");
        }}>Simulate payment success</button>
      </div>
      {paymentState === "PAYMENT_FAILED" ? <div role="alert">Payment failed in stub mode. Please retry payment.</div> : null}
    </ConnectStepShell>
  );
}

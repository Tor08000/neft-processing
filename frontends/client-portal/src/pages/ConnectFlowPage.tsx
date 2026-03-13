import { FormEvent, ReactNode, useMemo, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { createOrg } from "../api/clientPortal";
import { useAuth } from "../auth/AuthContext";
import { useClient } from "../auth/ClientContext";
import { useClientJourney } from "../auth/ClientJourneyContext";
import { CustomerType, getPlanByCode, getPlansByAudience } from "@shared/subscriptions/catalog";

export type ConnectProfileField = "fullName" | "legalName" | "phone" | "email" | "inn" | "kpp" | "ogrn" | "ogrnip" | "address" | "contact";
type ConnectProfileValues = Record<ConnectProfileField, string>;
type ConnectProfileErrors = Partial<Record<ConnectProfileField, string>>;

type ConnectStepKey = "plan" | "type" | "profile" | "documents" | "sign" | "payment";

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
  {
    code: "INDIVIDUAL",
    label: "Individual",
    description: "For personal use with minimal company details.",
    requirements: "You will need personal contacts and address.",
  },
  {
    code: "SOLE_PROPRIETOR",
    label: "Sole Proprietor",
    description: "For individual entrepreneurs registered as sole proprietors.",
    requirements: "Prepare INN and OGRNIP to continue.",
  },
  {
    code: "LEGAL_ENTITY",
    label: "Legal Entity",
    description: "For LLC/JSC and other corporate entities.",
    requirements: "Prepare legal company identifiers and legal address.",
  },
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

function ConnectStepShell({
  step,
  title,
  description,
  children,
  aside,
}: {
  step: ConnectStepKey;
  title: string;
  description: string;
  children: ReactNode;
  aside?: ReactNode;
}) {
  const stepIndex = CONNECT_STEPS.findIndex((item) => item.key === step);
  return (
    <section className="stack card neft-card" data-testid={`connect-step-${step}`}>
      <div className="stack" style={{ gap: 8 }}>
        <h1>{title}</h1>
        <p className="muted">{description}</p>
        <div className="muted" aria-label="wizard-progress">
          Step {stepIndex + 1} of {CONNECT_STEPS.length}: {CONNECT_STEPS[stepIndex]?.label}
        </div>
        <ol style={{ display: "grid", gridTemplateColumns: "repeat(3, minmax(0,1fr))", gap: 8, paddingLeft: 20, margin: 0 }}>
          {CONNECT_STEPS.map((item, index) => (
            <li key={item.key} style={{ fontWeight: item.key === step ? 700 : 400, opacity: index <= stepIndex ? 1 : 0.65 }}>
              {item.label}
            </li>
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
  return (
    <div className="card neft-card" style={{ marginTop: 8 }}>
      <strong>Connection summary</strong>
      <div className="muted">Current stage: {state}</div>
      <div className="muted">Next step: {nextRoute}</div>
      <div>Plan: {plan?.title ?? "Not selected"}</div>
      <div>Customer type: {draft.customerType ?? "Not selected"}</div>
    </div>
  );
}

export function ConnectHomePage() {
  const { state, nextRoute } = useClientJourney();
  return (
    <ConnectStepShell
      step="plan"
      title="Finish your company connection"
      description="Continue the onboarding wizard to unlock the full client cabinet and billing features."
      aside={<ConnectSummaryCard />}
    >
      <p>Current stage: {state}</p>
      <Link className="neft-button neft-btn-primary" to={nextRoute === "/connect" ? "/connect/plan" : nextRoute}>
        Continue setup
      </Link>
    </ConnectStepShell>
  );
}

export function ConnectPlanPage() {
  const { updateDraft, draft } = useClientJourney();
  const navigate = useNavigate();

  return (
    <ConnectStepShell
      step="plan"
      title="Choose your tariff"
      description="Select the plan that best matches your expected usage. You can change it before payment."
      aside={<ConnectSummaryCard />}
    >
      <div className="stack">
        {CLIENT_PLANS.map((plan) => {
          const isSelected = draft.selectedPlan === plan.code;
          return (
            <article key={plan.code} className="card neft-card stack" data-testid={`plan-card-${plan.code}`} style={{ borderColor: isSelected ? "#2e7d32" : undefined }}>
              <h2>
                {plan.title} {plan.badge ? <span className="muted">· {plan.badge}</span> : null}
              </h2>
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
    <ConnectStepShell
      step="type"
      title="Choose client type"
      description="This choice defines required profile fields and onboarding documents."
      aside={<ConnectSummaryCard />}
    >
      <div className="stack">
        {TYPE_DETAILS.map((type) => (
          <article key={type.code} className="card neft-card stack" data-testid={`type-option-${type.code}`} style={{ borderColor: draft.customerType === type.code ? "#2e7d32" : undefined }}>
            <h2>{type.label}</h2>
            <p>{type.description}</p>
            <p className="muted">{type.requirements}</p>
            <button
              className="neft-button neft-btn-secondary"
              onClick={() => {
                updateDraft({ customerType: type.code, profileCompleted: false });
                navigate("/connect/profile");
              }}
            >
              Continue as {type.label}
            </button>
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
        await createOrg(user, {
          org_type: orgType,
          name,
          inn: values.inn || "-",
          kpp: values.kpp || null,
          ogrn: values.ogrn || values.ogrnip || null,
          address: values.address || null,
        });
        await refresh();
      }
      updateDraft({ profileData: values, profileCompleted: true, documentsGenerated: false, documentsViewed: false });
      navigate("/connect/documents");
    } catch {
      setSubmitError("Unable to save profile. Check highlighted fields and try again.");
    }
  };

  if (!draft.customerType) {
    return (
      <ConnectStepShell
        step="profile"
        title="Profile details"
        description="Select client type before filling company details."
        aside={<ConnectSummaryCard />}
      >
        <Link to="/connect/type" className="neft-button neft-btn-primary">
          Go to client type
        </Link>
      </ConnectStepShell>
    );
  }

  return (
    <ConnectStepShell
      step="profile"
      title={draft.customerType === "LEGAL_ENTITY" ? "Company details" : "Personal details"}
      description="Fill only required fields for your selected client type."
      aside={<ConnectSummaryCard />}
    >
      <form onSubmit={onSubmit} className="stack">
        {submitError ? <div role="alert">{submitError}</div> : null}
        {requiredFields.map((field) => (
          <label key={field} className="stack" style={{ gap: 4 }}>
            <span>{PROFILE_FIELD_LABELS[field]} *</span>
            <input
              className="neft-input"
              value={values[field]}
              onChange={(event) => setField(field, event.target.value)}
              placeholder={PROFILE_FIELD_LABELS[field]}
              aria-invalid={Boolean(errors[field])}
            />
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
  const { draft, updateDraft } = useClientJourney();
  const plan = getPlanByCode(draft.selectedPlan);
  const navigate = useNavigate();

  const documentStates = [
    { name: "Service agreement", status: draft.documentsGenerated ? "ready to review" : "pending generation" },
    { name: "Data processing annex", status: draft.documentsViewed ? "reviewed" : draft.documentsGenerated ? "ready to review" : "pending generation" },
  ];

  return (
    <ConnectStepShell
      step="documents"
      title="Review onboarding documents"
      description="Document generation can be stubbed, but review status is tracked explicitly."
      aside={<ConnectSummaryCard />}
    >
      <p>Plan: {plan?.title ?? draft.selectedPlan ?? "Not selected"}</p>
      <p>Customer type: {draft.customerType ?? "Not selected"}</p>
      <ul>
        {documentStates.map((doc) => (
          <li key={doc.name}>
            {doc.name}: <strong>{doc.status}</strong> · <button className="neft-button neft-btn-secondary" type="button">Preview (stub)</button>
          </li>
        ))}
      </ul>
      <div style={{ display: "flex", gap: 8 }}>
        <button className="neft-button neft-btn-secondary" onClick={() => updateDraft({ documentsGenerated: true })}>Generate documents</button>
        <button
          className="neft-button neft-btn-primary"
          onClick={() => {
            updateDraft({ documentsGenerated: true, documentsViewed: true });
            navigate("/connect/sign");
          }}
        >
          Continue to signature
        </button>
      </div>
    </ConnectStepShell>
  );
}

export function ConnectSignPage() {
  const { draft, updateDraft } = useClientJourney();
  const navigate = useNavigate();
  const [accepted, setAccepted] = useState(Boolean(draft.signAccepted));
  const plan = getPlanByCode(draft.selectedPlan);

  return (
    <ConnectStepShell
      step="sign"
      title="Confirm and sign documents"
      description="By confirming, you accept the subscription terms and generated service documents."
      aside={<ConnectSummaryCard />}
    >
      <p>Subscription: {plan?.title ?? draft.selectedPlan ?? "Not selected"}</p>
      <label style={{ display: "flex", gap: 8 }}>
        <input type="checkbox" checked={accepted} onChange={(event) => setAccepted(event.target.checked)} />
        <span>I reviewed all onboarding documents and accept the terms.</span>
      </label>
      <button
        className="neft-button neft-btn-primary"
        disabled={!accepted}
        onClick={() => {
          const nextState = draft.selectedPlan === "CLIENT_FREE_TRIAL" ? "TRIAL_ACTIVE" : "PAYMENT_PENDING";
          updateDraft({ signAccepted: accepted, documentsSigned: true, subscriptionState: nextState });
          navigate(draft.selectedPlan === "CLIENT_FREE_TRIAL" ? "/dashboard" : "/connect/payment");
        }}
      >
        Sign and continue
      </button>
    </ConnectStepShell>
  );
}

export function ConnectPaymentPage() {
  const { draft, updateDraft } = useClientJourney();
  const navigate = useNavigate();
  const plan = getPlanByCode(draft.selectedPlan);

  return (
    <ConnectStepShell
      step="payment"
      title="Subscription payment"
      description="Finalize billing to activate full cabinet access."
      aside={<ConnectSummaryCard />}
    >
      <p>Selected plan: {plan?.title ?? draft.selectedPlan ?? "Not selected"}</p>
      <p>Billing period: Monthly</p>
      <p>Amount due: {plan?.monthlyPrice == null ? "Custom contract amount" : `₽${plan.monthlyPrice}`}</p>
      {plan?.yearlyDiscountText ? <p className="muted">Discount info: {plan.yearlyDiscountText}</p> : null}
      {plan?.isTrial ? <p className="muted">Trial plans skip payment and activate directly.</p> : null}
      <div style={{ display: "flex", gap: 8 }}>
        <button className="neft-button neft-btn-secondary" onClick={() => updateDraft({ subscriptionState: "PAYMENT_FAILED" })}>Simulate payment failure</button>
        <button
          className="neft-button neft-btn-primary"
          onClick={() => {
            updateDraft({ subscriptionState: "ACTIVE" });
            navigate("/dashboard");
          }}
        >
          Proceed to payment
        </button>
      </div>
    </ConnectStepShell>
  );
}

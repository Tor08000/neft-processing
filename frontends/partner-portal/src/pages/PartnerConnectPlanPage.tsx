import { getPlansByAudience } from "@shared/subscriptions/catalog";
import { useNavigate } from "react-router-dom";
import { usePartnerSubscription } from "../auth/PartnerSubscriptionContext";

const PARTNER_PLANS = getPlansByAudience("PARTNER");

export function PartnerConnectPlanPage() {
  const { draft, updateDraft } = usePartnerSubscription();
  const navigate = useNavigate();

  return (
    <div className="stack card">
      <h1>Partner subscription plan</h1>
      {PARTNER_PLANS.map((plan) => (
        <div key={plan.code} className="card stack">
          <h2>{plan.title}</h2>
          <div>{plan.monthlyPrice == null ? "Custom" : `₽${plan.monthlyPrice} / month`}</div>
          <div className="muted">{plan.yearlyDiscountText}</div>
          <ul>{plan.bullets.map((bullet) => <li key={bullet}>{bullet}</li>)}</ul>
          <button
            className="ghost"
            onClick={() => {
              updateDraft({ selectedPlan: plan.code, subscriptionState: "PAYMENT_PENDING" });
              navigate("/dashboard");
            }}
          >
            {draft.selectedPlan === plan.code ? "Selected" : "Choose"}
          </button>
        </div>
      ))}
    </div>
  );
}

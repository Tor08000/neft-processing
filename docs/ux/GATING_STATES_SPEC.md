# Gating states spec

## Access state mapping

| Access state | When it applies | Primary UI intent | Example CTA |
| --- | --- | --- | --- |
| OK | Access allowed | Render dashboard/feature | — |
| NEEDS_ONBOARDING | Org/partner inactive or legal profile not verified | Onboarding checklist | Go to onboarding/legal profile |
| NEEDS_PLAN | Subscription/plan missing | Plan selection/paywall | Choose plan |
| OVERDUE | Billing soft block (overdue) | Payment required | Open invoices |
| SUSPENDED | Billing hard block/suspended | Access paused | Contact support |
| FORBIDDEN_ROLE | Missing required role | Permission denied | Request access |
| MISSING_CAPABILITY | Feature not entitled/addon required | Module unavailable | Contact manager |
| COMING_SOON | Feature/settlement not finalized | Coming soon info | Back to dashboard |
| TECH_ERROR | 5xx/network/invalid JSON | Technical error | Retry later |

## Backend error code mapping

| Backend error code | Access state |
| --- | --- |
| billing_soft_blocked | OVERDUE |
| billing_hard_blocked | SUSPENDED |
| billing_suspended | SUSPENDED |
| feature_not_entitled | MISSING_CAPABILITY |
| org_not_active | NEEDS_ONBOARDING |
| legal_not_verified | NEEDS_ONBOARDING |
| settlement_not_finalized | COMING_SOON |
| admin_forbidden | FORBIDDEN_ROLE |

## Notes

- Business blocks (403/409 with the codes above) must render the corresponding state, not a generic error.
- Legacy code `addon_required` should be treated as `feature_not_entitled` on the frontend until fully removed.
- Dashboards should avoid loading snapshot data when the access state is not OK.

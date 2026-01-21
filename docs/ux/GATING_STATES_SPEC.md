# UX Gating States Spec

## AccessState (frontend enum)

| State | Meaning |
| --- | --- |
| `OK` | Access granted, render content. |
| `NEEDS_ONBOARDING` | Org/partner not active, onboarding incomplete. |
| `NEEDS_PLAN` | Subscription missing (no plan). |
| `OVERDUE` | Billing overdue, payment required. |
| `SUSPENDED` | Billing suspended, access paused. |
| `FORBIDDEN_ROLE` | Role does not allow access. |
| `MISSING_CAPABILITY` | Capability/entitlement is disabled. |
| `COMING_SOON` | Feature is not implemented yet. |
| `TECH_ERROR` | 5xx/network/parse errors. |

## State → UI mapping

| AccessState | UI |
| --- | --- |
| `NEEDS_ONBOARDING` | “Подключить компанию” / onboarding CTA. |
| `NEEDS_PLAN` | “Выбрать тариф” + “Связаться с менеджером”. |
| `OVERDUE` | “Оплатите счёт” + invoices link. |
| `SUSPENDED` | “Доступ приостановлен” + support/billing CTA. |
| `FORBIDDEN_ROLE` | “Недостаточно прав”. |
| `MISSING_CAPABILITY` | Paywall / “Недоступно по подписке”. |
| `COMING_SOON` | Coming soon placeholder. |
| `TECH_ERROR` | Error page with `request_id` / `correlation_id` + retry. |

## Canonical backend error codes → AccessState

| Error code | AccessState |
| --- | --- |
| `billing_soft_blocked` | `OVERDUE` |
| `billing_suspended` | `SUSPENDED` |
| `feature_not_entitled` | `MISSING_CAPABILITY` |
| `org_not_active` | `NEEDS_ONBOARDING` |
| `partner_not_verified` | `NEEDS_ONBOARDING` |
| `legal_not_verified` | `NEEDS_ONBOARDING` |
| `settlement_not_finalized` | `COMING_SOON` |
| `admin_forbidden` | `FORBIDDEN_ROLE` |

## Error payload format (403/409 example)

```json
{
  "error": "billing_soft_blocked",
  "message": "Subscription overdue",
  "request_id": "req-123",
  "details": {
    "org_id": "org-1",
    "invoice_id": "inv-1"
  }
}
```

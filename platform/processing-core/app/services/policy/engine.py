from __future__ import annotations

from typing import Iterable

from app.services.audit_service import _sanitize_token_for_audit, request_context_from_request, AuditService
from app.services.policy.actions import Action
from app.services.policy.actor import ActorContext
from app.services.policy.decisions import PolicyDecision
from app.services.policy.resources import ResourceContext


_ADMIN_FINANCE_ROLES = {"ADMIN_FINANCE", "SUPERADMIN"}
_ADMIN_ACCOUNTING_ROLES = {"ADMIN_ACCOUNTING", "SUPERADMIN"}
_ADMIN_EXPORT_ROLES = {"ADMIN_FINANCE", "ADMIN_ACCOUNTING", "SUPERADMIN"}
_CLIENT_ACK_ROLES = {"CLIENT_OWNER", "CLIENT_ADMIN"}
_ADMIN_CRM_ROLES = {"ADMIN", "FINANCE", "ADMIN_FINANCE", "SUPERADMIN"}


class PolicyAccessDenied(PermissionError):
    def __init__(self, decision: PolicyDecision):
        super().__init__(decision.reason or "access_denied")
        self.decision = decision


class PolicyEngine:
    def check(
        self,
        *,
        actor: ActorContext,
        action: Action,
        resource: ResourceContext,
    ) -> PolicyDecision:
        if action == Action.BILLING_PERIOD_FINALIZE:
            return self._billing_period_finalize(actor, resource)
        if action == Action.BILLING_PERIOD_LOCK:
            return self._billing_period_lock(actor, resource)
        if action == Action.INVOICE_ISSUE:
            return self._invoice_issue(actor, resource)
        if action == Action.INVOICE_ADJUST:
            return self._invoice_adjust(actor, resource)
        if action == Action.PAYMENT_APPLY:
            return self._payment_apply(actor, resource)
        if action == Action.CREDIT_NOTE_CREATE:
            return self._credit_note_create(actor, resource)
        if action == Action.PAYOUT_EXPORT_CREATE:
            return self._payout_export_create(actor, resource)
        if action == Action.PAYOUT_EXPORT_CONFIRM:
            return self._payout_export_confirm(actor, resource)
        if action == Action.ACCOUNTING_EXPORT_CREATE:
            return self._accounting_export_create(actor, resource)
        if action == Action.ACCOUNTING_EXPORT_CONFIRM:
            return self._accounting_export_confirm(actor, resource)
        if action == Action.DOCUMENT_ACKNOWLEDGE:
            return self._document_acknowledge(actor, resource)
        if action == Action.DOCUMENT_FINALIZE:
            return self._document_finalize(actor, resource)
        if action == Action.DOCUMENT_SEND_FOR_SIGNING:
            return self._document_send_for_signing(actor, resource)
        if action == Action.DOCUMENT_FINALIZE_WITH_SIGNATURE:
            return self._document_finalize_with_signature(actor, resource)
        if action == Action.DOCUMENT_VOID_AFTER_SIGNING:
            return self._document_void_after_signing(actor, resource)
        if action == Action.CLOSING_PACKAGE_ACK:
            return self._closing_package_ack(actor, resource)
        if action == Action.CLOSING_PACKAGE_FINALIZE:
            return self._closing_package_finalize(actor, resource)
        if action == Action.BILLING_PERIOD_REOPEN:
            return PolicyDecision(False, policy="billing_period_reopen_disabled", reason="action_disabled")
        if action in {
            Action.CRM_CLIENT_MANAGE,
            Action.CRM_CONTRACT_MANAGE,
            Action.CRM_TARIFF_MANAGE,
            Action.CRM_SUBSCRIPTION_MANAGE,
            Action.CRM_FEATURE_TOGGLE,
        }:
            return self._crm_manage(actor, resource)
        return PolicyDecision(False, policy="unsupported_action", reason="unsupported_action")

    @staticmethod
    def _has_role(actor: ActorContext, roles: Iterable[str]) -> bool:
        return bool(actor.roles.intersection(set(roles)))

    def _require_admin(self, actor: ActorContext, *, policy: str) -> PolicyDecision | None:
        if actor.actor_type != "ADMIN":
            return PolicyDecision(False, policy=policy, reason="actor_not_admin")
        return None

    def _billing_period_finalize(self, actor: ActorContext, resource: ResourceContext) -> PolicyDecision:
        if denial := self._require_admin(actor, policy="billing_period_finalize_admin_only"):
            return denial
        if not self._has_role(actor, _ADMIN_FINANCE_ROLES):
            return PolicyDecision(False, policy="billing_period_finalize_role", reason="missing_role")
        if resource.status != "OPEN":
            return PolicyDecision(False, policy="billing_period_finalize_status", reason="status_not_open")
        return PolicyDecision(True, policy="billing_period_finalize_allowed")

    def _billing_period_lock(self, actor: ActorContext, resource: ResourceContext) -> PolicyDecision:
        if denial := self._require_admin(actor, policy="billing_period_lock_admin_only"):
            return denial
        if not self._has_role(actor, _ADMIN_FINANCE_ROLES):
            return PolicyDecision(False, policy="billing_period_lock_role", reason="missing_role")
        if resource.status != "FINALIZED":
            return PolicyDecision(False, policy="billing_period_lock_status", reason="status_not_finalized")
        return PolicyDecision(True, policy="billing_period_lock_allowed")

    def _invoice_issue(self, actor: ActorContext, resource: ResourceContext) -> PolicyDecision:
        if denial := self._require_admin(actor, policy="invoice_issue_admin_only"):
            return denial
        if not self._has_role(actor, _ADMIN_FINANCE_ROLES):
            return PolicyDecision(False, policy="invoice_issue_role", reason="missing_role")
        if resource.status not in {"OPEN", None}:
            return PolicyDecision(False, policy="invoice_issue_status", reason="period_not_open")
        return PolicyDecision(True, policy="invoice_issue_allowed")

    def _invoice_adjust(self, actor: ActorContext, resource: ResourceContext) -> PolicyDecision:
        if denial := self._require_admin(actor, policy="invoice_adjust_admin_only"):
            return denial
        if not self._has_role(actor, {"ADMIN_FINANCE"}):
            return PolicyDecision(False, policy="invoice_adjust_role", reason="missing_role")
        if resource.status != "OPEN":
            return PolicyDecision(False, policy="invoice_adjust_status", reason="period_not_open")
        return PolicyDecision(True, policy="invoice_adjust_allowed")

    def _payment_apply(self, actor: ActorContext, resource: ResourceContext) -> PolicyDecision:
        if denial := self._require_admin(actor, policy="payment_apply_admin_only"):
            return denial
        if not self._has_role(actor, _ADMIN_FINANCE_ROLES):
            return PolicyDecision(False, policy="payment_apply_role", reason="missing_role")
        return PolicyDecision(True, policy="payment_apply_allowed")

    def _credit_note_create(self, actor: ActorContext, resource: ResourceContext) -> PolicyDecision:
        if denial := self._require_admin(actor, policy="credit_note_admin_only"):
            return denial
        if not self._has_role(actor, _ADMIN_FINANCE_ROLES):
            return PolicyDecision(False, policy="credit_note_role", reason="missing_role")
        return PolicyDecision(True, policy="credit_note_allowed")

    def _payout_export_create(self, actor: ActorContext, resource: ResourceContext) -> PolicyDecision:
        if denial := self._require_admin(actor, policy="payout_export_create_admin_only"):
            return denial
        if not self._has_role(actor, _ADMIN_FINANCE_ROLES):
            return PolicyDecision(False, policy="payout_export_create_role", reason="missing_role")
        if resource.status not in {"FINALIZED", "LOCKED"}:
            return PolicyDecision(False, policy="payout_export_create_status", reason="period_not_finalized")
        return PolicyDecision(True, policy="payout_export_create_allowed")

    def _payout_export_confirm(self, actor: ActorContext, resource: ResourceContext) -> PolicyDecision:
        if denial := self._require_admin(actor, policy="payout_export_confirm_admin_only"):
            return denial
        if not self._has_role(actor, _ADMIN_ACCOUNTING_ROLES):
            return PolicyDecision(False, policy="payout_export_confirm_role", reason="missing_role")
        return PolicyDecision(True, policy="payout_export_confirm_allowed")

    def _accounting_export_create(self, actor: ActorContext, resource: ResourceContext) -> PolicyDecision:
        if denial := self._require_admin(actor, policy="accounting_export_create_admin_only"):
            return denial
        if not self._has_role(actor, _ADMIN_EXPORT_ROLES):
            return PolicyDecision(False, policy="accounting_export_create_role", reason="missing_role")
        if resource.status not in {"FINALIZED", "LOCKED"}:
            return PolicyDecision(False, policy="accounting_export_create_status", reason="period_not_finalized")
        return PolicyDecision(True, policy="accounting_export_create_allowed")

    def _accounting_export_confirm(self, actor: ActorContext, resource: ResourceContext) -> PolicyDecision:
        if denial := self._require_admin(actor, policy="accounting_export_confirm_admin_only"):
            return denial
        if not self._has_role(actor, _ADMIN_EXPORT_ROLES):
            return PolicyDecision(False, policy="accounting_export_confirm_role", reason="missing_role")
        return PolicyDecision(True, policy="accounting_export_confirm_allowed")

    def _document_acknowledge(self, actor: ActorContext, resource: ResourceContext) -> PolicyDecision:
        if actor.actor_type == "SYSTEM":
            return PolicyDecision(True, policy="document_acknowledge_system")
        if actor.actor_type != "CLIENT":
            return PolicyDecision(False, policy="document_acknowledge_client_only", reason="actor_not_client")
        if not self._has_role(actor, _CLIENT_ACK_ROLES):
            return PolicyDecision(False, policy="document_acknowledge_role", reason="missing_role")
        if resource.status != "ISSUED":
            return PolicyDecision(False, policy="document_acknowledge_status", reason="status_not_issued")
        return PolicyDecision(True, policy="document_acknowledge_allowed")

    def _document_finalize(self, actor: ActorContext, resource: ResourceContext) -> PolicyDecision:
        if denial := self._require_admin(actor, policy="document_finalize_admin_only"):
            return denial
        if not self._has_role(actor, _ADMIN_FINANCE_ROLES):
            return PolicyDecision(False, policy="document_finalize_role", reason="missing_role")
        if resource.status != "ACKNOWLEDGED":
            return PolicyDecision(False, policy="document_finalize_status", reason="status_not_acknowledged")
        return PolicyDecision(True, policy="document_finalize_allowed")

    def _document_send_for_signing(self, actor: ActorContext, resource: ResourceContext) -> PolicyDecision:
        if denial := self._require_admin(actor, policy="document_send_for_signing_admin_only"):
            return denial
        if not self._has_role(actor, _ADMIN_FINANCE_ROLES):
            return PolicyDecision(False, policy="document_send_for_signing_role", reason="missing_role")
        if resource.status != "ISSUED":
            return PolicyDecision(False, policy="document_send_for_signing_status", reason="status_not_issued")
        return PolicyDecision(True, policy="document_send_for_signing_allowed")

    def _document_finalize_with_signature(self, actor: ActorContext, resource: ResourceContext) -> PolicyDecision:
        if denial := self._require_admin(actor, policy="document_finalize_with_signature_admin_only"):
            return denial
        if not self._has_role(actor, _ADMIN_FINANCE_ROLES):
            return PolicyDecision(False, policy="document_finalize_with_signature_role", reason="missing_role")
        if resource.status != "ACKNOWLEDGED":
            return PolicyDecision(False, policy="document_finalize_with_signature_status", reason="status_not_acknowledged")
        return PolicyDecision(True, policy="document_finalize_with_signature_allowed")

    def _document_void_after_signing(self, actor: ActorContext, resource: ResourceContext) -> PolicyDecision:
        if denial := self._require_admin(actor, policy="document_void_after_signing_admin_only"):
            return denial
        if not self._has_role(actor, _ADMIN_FINANCE_ROLES):
            return PolicyDecision(False, policy="document_void_after_signing_role", reason="missing_role")
        if resource.status not in {"ISSUED", "ACKNOWLEDGED"}:
            return PolicyDecision(False, policy="document_void_after_signing_status", reason="status_invalid")
        return PolicyDecision(True, policy="document_void_after_signing_allowed")

    def _closing_package_ack(self, actor: ActorContext, resource: ResourceContext) -> PolicyDecision:
        if actor.actor_type == "SYSTEM":
            return PolicyDecision(True, policy="closing_package_ack_system")
        if actor.actor_type != "CLIENT":
            return PolicyDecision(False, policy="closing_package_ack_client_only", reason="actor_not_client")
        if not self._has_role(actor, _CLIENT_ACK_ROLES):
            return PolicyDecision(False, policy="closing_package_ack_role", reason="missing_role")
        if resource.status != "ISSUED":
            return PolicyDecision(False, policy="closing_package_ack_status", reason="status_not_issued")
        return PolicyDecision(True, policy="closing_package_ack_allowed")

    def _closing_package_finalize(self, actor: ActorContext, resource: ResourceContext) -> PolicyDecision:
        if denial := self._require_admin(actor, policy="closing_package_finalize_admin_only"):
            return denial
        if not self._has_role(actor, _ADMIN_FINANCE_ROLES):
            return PolicyDecision(False, policy="closing_package_finalize_role", reason="missing_role")
        if resource.status != "ACKNOWLEDGED":
            return PolicyDecision(False, policy="closing_package_finalize_status", reason="status_not_acknowledged")
        return PolicyDecision(True, policy="closing_package_finalize_allowed")

    def _crm_manage(self, actor: ActorContext, resource: ResourceContext) -> PolicyDecision:
        if denial := self._require_admin(actor, policy="crm_manage_admin_only"):
            return denial
        if not self._has_role(actor, _ADMIN_CRM_ROLES):
            return PolicyDecision(False, policy="crm_manage_role", reason="missing_role")
        return PolicyDecision(True, policy="crm_manage_allowed")


def audit_access_denied(
    db,
    *,
    actor: ActorContext,
    action: Action,
    resource: ResourceContext,
    decision: PolicyDecision,
    token: dict | None,
) -> None:
    AuditService(db).audit(
        event_type="ACCESS_DENIED",
        entity_type="policy",
        entity_id=action.value,
        action="ACCESS_DENIED",
        after={
            "actor": {
                "actor_type": actor.actor_type,
                "tenant_id": actor.tenant_id,
                "client_id": actor.client_id,
                "roles": sorted(actor.roles),
                "user_id": actor.user_id,
            },
            "action": action.value,
            "resource": {
                "resource_type": resource.resource_type,
                "tenant_id": resource.tenant_id,
                "client_id": resource.client_id,
                "status": resource.status,
            },
            "policy": decision.policy,
            "reason": decision.reason,
        },
        reason=decision.reason,
        request_ctx=request_context_from_request(None, token=_sanitize_token_for_audit(token)),
    )


__all__ = ["PolicyAccessDenied", "PolicyEngine", "audit_access_denied"]

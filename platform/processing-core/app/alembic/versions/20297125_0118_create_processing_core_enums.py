"""Create canonical enum types for processing core and bi schemas.

Revision ID: 20297125_0118_create_processing_core_enums
Revises: 20297120_0117_create_core_base_tables_v1
Create Date: 2029-07-25 00:00:00.000000
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa

from app.alembic.helpers import ensure_pg_enum
from app.alembic.utils import is_postgres
from app.db.schema import resolve_db_schema

# revision identifiers, used by Alembic.
revision = "20297125_0118_create_processing_core_enums"
down_revision = "20297120_0117_create_core_base_tables_v1"  # keep 0117 in ancestry
branch_labels = None
depends_on = None

SCHEMA_RESOLUTION = resolve_db_schema()
PROCESSING_SCHEMA = SCHEMA_RESOLUTION.schema
BI_SCHEMA = "bi"

PROCESSING_ENUMS = {
    'accounting_export_format': ('CSV', 'JSON'),
    'accounting_export_state': ('CREATED', 'GENERATED', 'UPLOADED', 'DOWNLOADED', 'CONFIRMED', 'FAILED'),
    'accounting_export_type': ('CHARGES', 'SETTLEMENT'),
    'accountownertype': ('CLIENT', 'PARTNER', 'PLATFORM'),
    'accountstatus': ('ACTIVE', 'FROZEN', 'CLOSED'),
    'accounttype': ('CLIENT_MAIN', 'CLIENT_CREDIT', 'CARD_LIMIT', 'TECHNICAL'),
    'audit_actor_type': ('USER', 'SERVICE', 'SYSTEM'),
    'audit_visibility': ('PUBLIC', 'INTERNAL'),
    'bank_stub_payment_status': ('CREATED', 'POSTED', 'SETTLED', 'REVERSED'),
    'billing_invoice_status': ('ISSUED', 'PARTIALLY_PAID', 'PAID', 'VOID'),
    'billing_job_status': ('STARTED', 'SUCCESS', 'FAILED'),
    'billing_job_type': ('BILLING_DAILY', 'BILLING_FINALIZE', 'SUBSCRIPTION_BILLING', 'INVOICE_MONTHLY', 'RECONCILIATION', 'MANUAL_RUN', 'PDF_GENERATE', 'INVOICE_SEND', 'CREDIT_NOTE_PDF', 'FINANCE_EXPORT', 'BALANCE_REBUILD', 'CLEARING', 'CLEARING_RUN', 'FINANCE_PAYMENT', 'FINANCE_CREDIT_NOTE', 'BILLING_SEED'),
    'billing_payment_status': ('CAPTURED', 'FAILED', 'REFUNDED_PARTIAL', 'REFUNDED_FULL'),
    'billing_period_status': ('OPEN', 'FINALIZED', 'LOCKED'),
    'billing_period_type': ('DAILY', 'MONTHLY', 'ADHOC'),
    'billing_reconciliation_status': ('OK', 'FAILED', 'PARTIAL'),
    'billing_reconciliation_verdict': ('OK', 'MISMATCH', 'MISSING_LEDGER', 'ERROR'),
    'billing_refund_status': ('REFUNDED', 'FAILED'),
    'billing_task_status': ('QUEUED', 'RUNNING', 'SUCCESS', 'FAILED'),
    'billing_task_type': ('MONTHLY_RUN', 'PDF_GENERATE', 'INVOICE_SEND'),
    'billingsummarystatus': ('PENDING', 'FINALIZED'),
    'case_comment_type': ('user', 'system'),
    'case_event_type': ('CASE_CREATED', 'STATUS_CHANGED', 'CASE_CLOSED', 'NOTE_UPDATED', 'ACTIONS_APPLIED', 'EXPORT_CREATED', 'CARD_CREATED', 'CARD_STATUS_CHANGED', 'GROUP_CREATED', 'GROUP_MEMBER_ADDED', 'GROUP_MEMBER_REMOVED', 'GROUP_ACCESS_GRANTED', 'GROUP_ACCESS_REVOKED', 'LIMIT_SET', 'LIMIT_REVOKED', 'TRANSACTION_INGESTED', 'TRANSACTION_IMPORTED', 'FLEET_TRANSACTIONS_INGESTED', 'FLEET_INGEST_FAILED', 'FUEL_LIMIT_BREACH_DETECTED', 'FUEL_ANOMALY_DETECTED', 'FUEL_CARD_AUTO_BLOCKED', 'FUEL_CARD_UNBLOCKED', 'FLEET_POLICY_ACTION_APPLIED', 'FLEET_POLICY_ACTION_FAILED', 'FLEET_ESCALATION_CASE_CREATED', 'FLEET_ACTION_POLICY_CREATED', 'FLEET_ACTION_POLICY_DISABLED', 'FLEET_ALERT_STATUS_UPDATED', 'FLEET_NOTIFICATION_CHANNEL_CREATED', 'FLEET_NOTIFICATION_CHANNEL_DISABLED', 'FLEET_NOTIFICATION_POLICY_CREATED', 'FLEET_NOTIFICATION_POLICY_DISABLED', 'FLEET_NOTIFICATION_ENQUEUED', 'FLEET_TELEGRAM_LINK_TOKEN_ISSUED', 'FLEET_TELEGRAM_BOUND', 'FLEET_TELEGRAM_UNBOUND', 'FLEET_TELEGRAM_SEND_FAILED', 'SLA_ESCALATION_CASE_CREATED', 'INVOICE_ISSUED', 'PAYMENT_CAPTURED', 'PAYMENT_REFUNDED', 'INVOICE_STATUS_CHANGED', 'EXTERNAL_RECONCILIATION_COMPLETED', 'SETTLEMENT_CALCULATED', 'SETTLEMENT_APPROVED', 'PAYOUT_INITIATED', 'PAYOUT_CONFIRMED', 'MARKETPLACE_ORDER_CREATED', 'MARKETPLACE_ORDER_ACCEPTED', 'MARKETPLACE_ORDER_REJECTED', 'MARKETPLACE_ORDER_STARTED', 'MARKETPLACE_ORDER_PROGRESS_UPDATED', 'MARKETPLACE_ORDER_COMPLETED', 'MARKETPLACE_ORDER_FAILED', 'MARKETPLACE_ORDER_CANCELLED', 'BOOKING_CREATED', 'SLOT_LOCKED', 'BOOKING_CONFIRMED', 'BOOKING_DECLINED', 'BOOKING_CANCELED', 'BOOKING_STATUS_CHANGED', 'BOOKING_COMPLETED', 'SERVICE_RECORD_CREATED'),
    'case_export_kind': ('EXPLAIN', 'DIFF', 'CASE'),
    'case_kind': ('operation', 'invoice', 'order', 'kpi', 'fleet', 'booking'),
    'case_priority': ('LOW', 'MEDIUM', 'HIGH', 'CRITICAL'),
    'case_queue': ('FRAUD_OPS', 'FINANCE_OPS', 'SUPPORT', 'GENERAL'),
    'case_status': ('TRIAGE', 'IN_PROGRESS', 'RESOLVED', 'CLOSED'),
    'clearing_batch_state': ('OPEN', 'CLOSED'),
    'clearing_batch_status': ('PENDING', 'SENT', 'CONFIRMED', 'FAILED'),
    'clearing_status': ('PENDING',),
    'closing_package_status': ('DRAFT', 'ISSUED', 'ACKNOWLEDGED', 'FINALIZED', 'VOID'),
    'coupon_status': ('NEW', 'ISSUED', 'REDEEMED', 'EXPIRED', 'CANCELED'),
    'credit_note_status': ('POSTED', 'FAILED', 'REVERSED'),
    'crm_billing_cycle': ('MONTHLY',),
    'crm_billing_mode': ('POSTPAID', 'PREPAID'),
    'crm_billing_period': ('MONTHLY', 'YEARLY'),
    'crm_client_status': ('ACTIVE', 'SUSPENDED', 'CLOSED'),
    'crm_contract_status': ('DRAFT', 'ACTIVE', 'PAUSED', 'TERMINATED'),
    'crm_feature_flag': ('FUEL_ENABLED', 'LOGISTICS_ENABLED', 'DOCUMENTS_ENABLED', 'RISK_BLOCKING_ENABLED', 'ACCOUNTING_EXPORT_ENABLED', 'SUBSCRIPTION_METER_FUEL_ENABLED', 'CASES_ENABLED'),
    'crm_profile_status': ('ACTIVE', 'ARCHIVED'),
    'crm_subscription_charge_type': ('BASE_FEE', 'OVERAGE'),
    'crm_subscription_segment_reason': ('START', 'UPGRADE', 'DOWNGRADE', 'PAUSE', 'RESUME', 'CANCEL'),
    'crm_subscription_segment_status': ('ACTIVE', 'PAUSED'),
    'crm_subscription_status': ('ACTIVE', 'PAUSED', 'CANCELLED'),
    'crm_tariff_status': ('ACTIVE', 'ARCHIVED'),
    'crm_usage_metric': ('CARDS_COUNT', 'VEHICLES_COUNT', 'DRIVERS_COUNT', 'FUEL_TX_COUNT', 'FUEL_VOLUME', 'LOGISTICS_ORDERS'),
    'decision_memory_effect_label': ('IMPROVED', 'NO_CHANGE', 'WORSE', 'UNKNOWN'),
    'decision_memory_entity_type': ('DRIVER', 'VEHICLE', 'STATION', 'CLIENT'),
    'dispute_event_type': ('OPENED', 'MOVED_TO_REVIEW', 'ACCEPTED', 'REJECTED', 'CLOSED', 'HOLD_PLACED', 'HOLD_RELEASED', 'REFUND_POSTED', 'FEE_POSTED'),
    'dispute_status': ('OPEN', 'UNDER_REVIEW', 'ACCEPTED', 'REJECTED', 'CLOSED'),
    'document_envelope_status': ('CREATED', 'SENT', 'DELIVERED', 'SIGNED', 'DECLINED', 'EXPIRED', 'FAILED'),
    'document_file_type': ('PDF', 'XLSX', 'SIG', 'P7S', 'CERT', 'EDI_XML'),
    'document_signature_status': ('REQUESTED', 'SIGNING', 'SIGNED', 'FAILED', 'VERIFIED', 'REJECTED'),
    'document_status': ('DRAFT', 'ISSUED', 'ACKNOWLEDGED', 'FINALIZED', 'VOID'),
    'document_type': ('INVOICE', 'SUBSCRIPTION_INVOICE', 'SUBSCRIPTION_ACT', 'ACT', 'RECONCILIATION_ACT', 'CLOSING_PACKAGE', 'OFFER'),
    'edo_document_status': ('QUEUED', 'UPLOADING', 'SENT', 'DELIVERED', 'SIGNED_BY_US', 'SIGNED_BY_COUNTERPARTY', 'REJECTED', 'FAILED'),
    'edo_provider': ('DIADOK', 'SBIS'),
    'employee_status': ('ACTIVE', 'INVITED', 'DISABLED'),
    'erp_counterparty_ref_mode': ('INN_KPP', 'ERP_ID', 'NAME'),
    'erp_delivery_mode': ('S3_PULL', 'WEBHOOK_PUSH', 'SFTP_PUSH', 'API_PUSH'),
    'erp_export_format': ('CSV', 'JSON', 'XML_1C'),
    'erp_mapping_match_kind': ('DOC_TYPE', 'SERVICE_CODE', 'PRODUCT_TYPE', 'COMMISSION_KIND', 'TAX_RATE', 'PARTNER', 'CUSTOM'),
    'erp_mapping_status': ('DRAFT', 'ACTIVE', 'ARCHIVED'),
    'erp_reconciliation_status': ('REQUESTED', 'IN_PROGRESS', 'OK', 'MISMATCH', 'FAILED'),
    'erp_reconciliation_verdict': ('OK', 'MISSING_IN_ERP', 'EXTRA_IN_ERP', 'AMOUNT_DIFF', 'TAX_DIFF'),
    'erp_stub_export_status': ('CREATED', 'SENT', 'ACKED', 'FAILED'),
    'erp_stub_export_type': ('INVOICES', 'PAYMENTS', 'SETTLEMENT', 'RECONCILIATION'),
    'erp_system_type': ('1C', 'SAP', 'GENERIC'),
    'fi_action_code': ('SUGGEST_LIMIT_PROFILE_SAFE', 'SUGGEST_RESTRICT_NIGHT_FUELING', 'SUGGEST_REQUIRE_ROUTE_LINKED_REFUEL', 'SUGGEST_EXCLUDE_STATION_FROM_ROUTES', 'SUGGEST_VEHICLE_DIAGNOSTIC'),
    'fi_action_effect_label': ('IMPROVED', 'NO_CHANGE', 'WORSE'),
    'fi_action_target_system': ('CRM', 'LOGISTICS', 'OPS'),
    'fi_applied_action_status': ('SUCCESS', 'FAILED'),
    'fi_driver_behavior_level': ('LOW', 'MEDIUM', 'HIGH', 'VERY_HIGH'),
    'fi_insight_entity_type': ('DRIVER', 'VEHICLE', 'STATION'),
    'fi_insight_severity': ('LOW', 'MEDIUM', 'HIGH', 'CRITICAL'),
    'fi_insight_status': ('OPEN', 'ACKED', 'ACTION_PLANNED', 'ACTION_APPLIED', 'MONITORING', 'RESOLVED', 'IGNORED'),
    'fi_insight_type': ('DRIVER_BEHAVIOR_DEGRADING', 'STATION_TRUST_DEGRADING', 'VEHICLE_EFFICIENCY_DEGRADING'),
    'fi_station_trust_level': ('TRUSTED', 'WATCHLIST', 'BLACKLIST'),
    'fi_suggested_action_status': ('PROPOSED', 'APPROVED', 'REJECTED', 'APPLIED'),
    'fi_trend_entity_type': ('DRIVER', 'VEHICLE', 'STATION'),
    'fi_trend_label': ('IMPROVING', 'STABLE', 'DEGRADING', 'UNKNOWN'),
    'fi_trend_metric': ('DRIVER_BEHAVIOR_SCORE', 'STATION_TRUST_SCORE', 'VEHICLE_EFFICIENCY_DELTA_PCT'),
    'fi_trend_window': ('D7', 'D30', 'ROLLING'),
    'financial_adjustment_kind': ('REFUND_ADJUSTMENT', 'REVERSAL_ADJUSTMENT', 'DISPUTE_ADJUSTMENT', 'FEE_ADJUSTMENT', 'CREDIT', 'DEBIT'),
    'financial_adjustment_related': ('REFUND', 'REVERSAL', 'DISPUTE', 'BILLING_PERIOD'),
    'financial_adjustment_status': ('PENDING', 'POSTED', 'FAILED'),
    'fleet_driver_status': ('ACTIVE', 'INACTIVE'),
    'fleet_notification_channel_status': ('ACTIVE', 'DISABLED'),
    'fleet_notification_event_type': ('LIMIT_BREACH', 'ANOMALY', 'INGEST_FAILED', 'DAILY_SUMMARY', 'POLICY_ACTION', 'TEST'),
    'fleet_notification_scope_type': ('client', 'group', 'card'),
    'fleet_notification_severity': ('LOW', 'MEDIUM', 'HIGH', 'CRITICAL'),
    'fleet_vehicle_status': ('ACTIVE', 'INACTIVE'),
    'fuel_limit_escalation_action': ('NOTIFY_ONLY', 'AUTO_BLOCK_CARD', 'SUSPEND_GROUP'),
    'fuel_group_role': ('viewer', 'manager', 'admin'),
    'fuelproducttype': ('ANY', 'DIESEL', 'AI92', 'AI95', 'AI98', 'GAS', 'OTHER'),
    'internal_ledger_account_status': ('ACTIVE', 'ARCHIVED'),
    'internal_ledger_account_type': ('CLIENT_AR', 'CLIENT_CASH', 'PLATFORM_REVENUE', 'PLATFORM_FEES', 'TAX_VAT', 'PROVIDER_PAYABLE', 'SUSPENSE', 'SETTLEMENT_CLEARING', 'PARTNER_SETTLEMENT'),
    'internal_ledger_entry_direction': ('DEBIT', 'CREDIT'),
    'internal_ledger_transaction_type': ('INVOICE_ISSUED', 'PAYMENT_APPLIED', 'CREDIT_NOTE_APPLIED', 'REFUND_APPLIED', 'SETTLEMENT_ALLOCATION_CREATED', 'ACCOUNTING_EXPORT_CONFIRMED', 'FUEL_SETTLEMENT', 'FUEL_REVERSAL', 'ADJUSTMENT', 'PARTNER_PAYOUT'),
    'invoice_message_sender_type': ('CLIENT', 'SUPPORT', 'SYSTEM'),
    'invoice_payment_status': ('POSTED', 'FAILED'),
    'invoice_pdf_status': ('NONE', 'QUEUED', 'GENERATING', 'READY', 'FAILED'),
    'invoice_thread_status': ('OPEN', 'WAITING_SUPPORT', 'WAITING_CLIENT', 'RESOLVED', 'CLOSED'),
    'invoicestatus': ('DRAFT', 'ISSUED', 'SENT', 'PARTIALLY_PAID', 'PAID', 'OVERDUE', 'CANCELLED', 'CREDITED'),
    'ledgerdirection': ('DEBIT', 'CREDIT'),
    'legal_edge_type': ('GENERATED_FROM', 'CONFIRMS', 'CLOSES', 'INCLUDES', 'RELATES_TO', 'SIGNED_BY', 'RISK_GATED_BY', 'GATED_BY_RISK', 'SETTLES', 'EXPORTS', 'REPLACES', 'ALLOCATES', 'OVERRIDDEN_BY'),
    'legal_graph_snapshot_scope': ('DOCUMENT', 'CLOSING_PACKAGE', 'BILLING_PERIOD'),
    'legal_node_type': ('DOCUMENT', 'DOCUMENT_FILE', 'DOCUMENT_ACK', 'CLOSING_PACKAGE', 'BILLING_PERIOD', 'INVOICE', 'SUBSCRIPTION', 'PAYMENT', 'CREDIT_NOTE', 'REFUND', 'SETTLEMENT_ALLOCATION', 'ACCOUNTING_EXPORT_BATCH', 'RISK_DECISION', 'OFFER', 'FUEL_TRANSACTION', 'CARD', 'FUEL_STATION', 'VEHICLE', 'DRIVER', 'FUEL_LIMIT', 'LOGISTICS_ORDER', 'LOGISTICS_ROUTE', 'LOGISTICS_STOP', 'FRAUD_SIGNAL'),
    'limitconfigscope': ('GLOBAL', 'CLIENT', 'CARD', 'TARIFF'),
    'limitentitytype': ('CLIENT', 'CARD', 'TERMINAL', 'MERCHANT'),
    'limitscope': ('PER_TX', 'DAILY', 'MONTHLY'),
    'limittype': ('DAILY_VOLUME', 'DAILY_AMOUNT', 'MONTHLY_AMOUNT', 'CREDIT_LIMIT'),
    'limitwindow': ('PER_TX', 'DAILY', 'MONTHLY'),
    'logistics_deviation_event_type': ('OFF_ROUTE', 'BACK_ON_ROUTE', 'STOP_OUT_OF_RADIUS', 'UNEXPECTED_STOP'),
    'logistics_deviation_severity': ('LOW', 'MEDIUM', 'HIGH'),
    'logistics_eta_method': ('PLANNED', 'SIMPLE_SPEED', 'LAST_KNOWN', 'HISTORICAL'),
    'logistics_fuel_link_type': ('AUTO_MATCH', 'MANUAL', 'PROVIDER'),
    'logistics_navigator_explain_type': ('ETA', 'DEVIATION'),
    'logistics_order_status': ('DRAFT', 'PLANNED', 'IN_PROGRESS', 'COMPLETED', 'CANCELLED'),
    'logistics_order_type': ('DELIVERY', 'SERVICE', 'TRIP'),
    'logistics_risk_signal_type': ('FUEL_OFF_ROUTE', 'FUEL_STOP_MISMATCH', 'ROUTE_DEVIATION_HIGH', 'ETA_ANOMALY', 'VELOCITY_ANOMALY'),
    'logistics_route_status': ('DRAFT', 'ACTIVE', 'ARCHIVED'),
    'logistics_stop_status': ('PENDING', 'ARRIVED', 'DEPARTED', 'SKIPPED'),
    'logistics_stop_type': ('START', 'WAYPOINT', 'FUEL', 'DELIVERY', 'END'),
    'logistics_tracking_event_type': ('LOCATION', 'STATUS_CHANGE', 'STOP_ARRIVAL', 'STOP_DEPARTURE', 'FUEL_STOP_LINKED'),
    'marketplace_coupon_batch_type': ('PUBLIC', 'TARGETED'),
    'marketplace_coupon_status': ('NEW', 'ISSUED', 'REDEEMED', 'EXPIRED', 'CANCELED'),
    'marketplace_event_type': ('VIEW', 'CLICK', 'ADD_TO_CART', 'PURCHASE', 'REFUND'),
    'marketplace_order_actor_type': ('client', 'partner', 'admin', 'system'),
    'marketplace_order_event_type': ('ORDER_CREATED', 'ORDER_ACCEPTED', 'ORDER_REJECTED', 'ORDER_STARTED', 'ORDER_PROGRESS_UPDATED', 'ORDER_COMPLETED', 'ORDER_FAILED', 'ORDER_CANCELLED', 'ORDER_NOTE_ADDED', 'MARKETPLACE_ORDER_CREATED', 'MARKETPLACE_ORDER_CONFIRMED_BY_PARTNER', 'MARKETPLACE_ORDER_STARTED', 'MARKETPLACE_ORDER_COMPLETED', 'MARKETPLACE_ORDER_FAILED'),
    'marketplace_order_status': ('CREATED', 'ACCEPTED', 'REJECTED', 'IN_PROGRESS', 'COMPLETED', 'FAILED', 'CANCELLED'),
    'marketplace_price_model': ('FIXED', 'PER_UNIT', 'TIERED'),
    'marketplace_product_moderation_status': ('DRAFT', 'PENDING_REVIEW', 'APPROVED', 'REJECTED'),
    'marketplace_product_status': ('DRAFT', 'PUBLISHED', 'ARCHIVED'),
    'marketplace_product_type': ('SERVICE', 'PRODUCT'),
    'marketplace_promotion_status': ('DRAFT', 'ACTIVE', 'PAUSED', 'ENDED', 'ARCHIVED'),
    'marketplace_promotion_type': ('PRODUCT_DISCOUNT', 'CATEGORY_DISCOUNT', 'PARTNER_STORE_DISCOUNT', 'COUPON_PROMO'),
    'marketplace_sla_notification_status': ('PENDING', 'SENT', 'FAILED'),
    'money_flow_event_type': ('AUTHORIZE', 'SETTLE', 'REVERSE', 'DISPUTE_OPEN', 'DISPUTE_RESOLVE', 'FAIL', 'CANCEL'),
    'money_flow_link_node_type': ('SUBSCRIPTION', 'SUBSCRIPTION_SEGMENT', 'SUBSCRIPTION_CHARGE', 'USAGE_COUNTER', 'INVOICE', 'DOCUMENT', 'PAYMENT', 'REFUND', 'FUEL_TX', 'LOGISTICS_ORDER', 'ACCOUNTING_EXPORT', 'LEDGER_TX', 'BILLING_PERIOD'),
    'money_flow_link_type': ('GENERATES', 'SETTLES', 'POSTS', 'FEEDS', 'RELATES'),
    'money_flow_state': ('DRAFT', 'AUTHORIZED', 'PENDING_SETTLEMENT', 'SETTLED', 'REVERSED', 'DISPUTED', 'FAILED', 'CANCELLED'),
    'money_flow_type': ('FUEL_TX', 'SUBSCRIPTION_CHARGE', 'INVOICE_PAYMENT', 'REFUND', 'PAYOUT'),
    'money_invariant_snapshot_phase': ('BEFORE', 'AFTER'),
    'operationstatus': ('PENDING', 'AUTHORIZED', 'HELD', 'COMPLETED', 'REVERSED', 'REFUNDED', 'DECLINED', 'CANCELLED', 'CAPTURED', 'OPEN'),
    'operationtype': ('AUTH', 'HOLD', 'COMMIT', 'REVERSE', 'REFUND', 'DECLINE', 'CAPTURE', 'REVERSAL'),
    'ops_escalation_primary_reason': ('LIMIT', 'RISK', 'LOGISTICS', 'MONEY', 'POLICY', 'UNKNOWN'),
    'ops_escalation_priority': ('LOW', 'MEDIUM', 'HIGH', 'CRITICAL'),
    'ops_escalation_source': ('AUTO_SLA_EXPIRED', 'MANUAL_FROM_EXPLAIN', 'SYSTEM'),
    'ops_escalation_status': ('OPEN', 'ACK', 'CLOSED'),
    'ops_escalation_target': ('CRM', 'COMPLIANCE', 'LOGISTICS', 'FINANCE'),
    'order_sla_consequence_status': ('APPLIED', 'FAILED'),
    'order_sla_consequence_type': ('PENALTY_FEE', 'CREDIT_NOTE', 'REFUND'),
    'order_sla_severity': ('LOW', 'MEDIUM', 'HIGH', 'CRITICAL'),
    'order_sla_status': ('OK', 'VIOLATION'),
    'partner_mission_status': ('ACTIVE', 'COMPLETED', 'CLAIMED', 'EXPIRED'),
    'partner_subscription_billing_cycle': ('monthly', 'yearly'),
    'partner_subscription_status': ('active', 'suspended', 'canceled'),
    'partner_verification_status': ('PENDING', 'VERIFIED', 'REJECTED'),
    'payout_batch_state': ('DRAFT', 'READY', 'SENT', 'SETTLED', 'FAILED'),
    'payout_export_format': ('CSV', 'XLSX'),
    'payout_export_state': ('DRAFT', 'GENERATED', 'UPLOADED', 'FAILED', 'STALE'),
    'payout_order_status': ('QUEUED', 'SENT', 'CONFIRMED', 'FAILED'),
    'payout_status': ('INITIATED', 'SENT', 'CONFIRMED', 'FAILED'),
    'plan_billing_period': ('MONTHLY', 'ANNUAL'),
    'plan_feature_code': ('FLEET_CARDS', 'GROUPS', 'LIMITS', 'ALERTS', 'WEBHOOK', 'PUSH', 'WHITE_LABEL', 'SLA'),
    'postingbatchstatus': ('APPLIED', 'REVERSED'),
    'postingbatchtype': ('AUTH', 'HOLD', 'COMMIT', 'CAPTURE', 'REFUND', 'REVERSAL', 'DISPUTE_HOLD', 'DISPUTE_RELEASE', 'ADJUSTMENT'),
    'producttype': ('DIESEL', 'AI92', 'AI95', 'AI98', 'GAS', 'OTHER'),
    'promo_budget_model': ('CPA', 'CPC'),
    'promo_budget_status': ('ACTIVE', 'PAUSED', 'EXHAUSTED'),
    'promotion_status': ('DRAFT', 'ACTIVE', 'PAUSED', 'ENDED', 'ARCHIVED'),
    'promotion_type': ('PRODUCT_DISCOUNT', 'CATEGORY_DISCOUNT', 'BUNDLE_DISCOUNT', 'TIER_DISCOUNT', 'PUBLIC_COUPON', 'TARGETED_COUPON', 'AUTO_COUPON', 'FLASH_SALE', 'HAPPY_HOURS', 'SPONSORED_PLACEMENT'),
    'reconciliation_discrepancy_status': ('open', 'resolved', 'ignored'),
    'reconciliation_discrepancy_type': ('balance_mismatch', 'missing_entry', 'duplicate_entry', 'unmatched_external', 'unmatched_internal', 'fx_not_supported', 'mismatched_amount'),
    'reconciliation_link_direction': ('IN', 'OUT'),
    'reconciliation_link_status': ('pending', 'matched', 'mismatched'),
    'reconciliation_request_status': ('REQUESTED', 'IN_PROGRESS', 'GENERATED', 'SENT', 'ACKNOWLEDGED', 'REJECTED', 'CANCELLED'),
    'reconciliation_run_scope': ('internal', 'external'),
    'reconciliation_run_status': ('started', 'completed', 'failed'),
    'refund_request_status': ('REQUESTED', 'POSTED', 'FAILED', 'CANCELLED'),
    'reversal_status': ('REQUESTED', 'POSTED', 'FAILED', 'CANCELLED'),
    'risk_score_action': ('PAYMENT', 'INVOICE', 'PAYOUT'),
    'riskdecision': ('ALLOW', 'ALLOW_WITH_REVIEW', 'BLOCK', 'ESCALATE'),
    'riskdecisionactor': ('SYSTEM', 'ADMIN'),
    'risklevel': ('LOW', 'MEDIUM', 'HIGH', 'VERY_HIGH'),
    'riskresult': ('LOW', 'MEDIUM', 'HIGH', 'BLOCK', 'MANUAL_REVIEW'),
    'riskruleaction': ('HARD_DECLINE', 'SOFT_FLAG', 'TARIFF_LIMIT', 'LOW', 'MEDIUM', 'HIGH', 'BLOCK', 'MANUAL_REVIEW'),
    'riskruleauditaction': ('CREATE', 'UPDATE', 'ENABLE', 'DISABLE'),
    'riskrulescope': ('GLOBAL', 'CLIENT', 'CARD', 'TARIFF', 'SEGMENT'),
    'risksubjecttype': ('PAYMENT', 'INVOICE', 'PAYOUT', 'DOCUMENT', 'EXPORT', 'FUEL_TRANSACTION'),
    'riskthresholdaction': ('PAYMENT', 'INVOICE', 'PAYOUT', 'EXPORT', 'DOCUMENT_FINALIZE'),
    'riskthresholdscope': ('GLOBAL', 'TENANT', 'CLIENT'),
    'riskv5label': ('FRAUD', 'NOT_FRAUD', 'UNKNOWN'),
    'riskv5labelsource': ('OVERRIDE', 'DISPUTE', 'CHARGEBACK', 'ANOMALY'),
    'settlement_account_status': ('ACTIVE', 'SUSPENDED'),
    'settlement_item_direction': ('IN', 'OUT'),
    'settlement_item_source_type': ('invoice', 'payment', 'refund', 'adjustment'),
    'settlement_period_status': ('OPEN', 'CALCULATED', 'APPROVED', 'PAID'),
    'settlement_policy': ('SAME_PERIOD', 'ADJUSTMENT_REQUIRED'),
    'settlement_source_type': ('PAYMENT', 'CREDIT_NOTE', 'REFUND'),
    'settlement_status': ('DRAFT', 'APPROVED', 'SENT', 'CONFIRMED', 'FAILED'),
    'signature_type': ('ESIGN', 'KEP', 'GOST_P7S', 'EDI_SIGN'),
    'sponsored_campaign_objective': ('CPC', 'CPA'),
    'sponsored_campaign_status': ('DRAFT', 'ACTIVE', 'PAUSED', 'ENDED', 'EXHAUSTED'),
    'sponsored_event_type': ('IMPRESSION', 'CLICK', 'CONVERSION'),
    'sponsored_spend_direction': ('DEBIT', 'CREDIT'),
    'sponsored_spend_type': ('CPC_CLICK', 'CPA_ORDER'),
    'subscription_module_code': ('FUEL_CORE', 'AI_ASSISTANT', 'EXPLAIN', 'PENALTIES', 'MARKETPLACE', 'ANALYTICS', 'SLA', 'BONUSES'),
    'subscription_status': ('FREE', 'ACTIVE', 'PAST_DUE', 'SUSPENDED', 'PENDING', 'PAUSED', 'GRACE', 'EXPIRED', 'CANCELLED'),
    'support_request_priority': ('LOW', 'NORMAL', 'HIGH'),
    'support_request_scope_type': ('CLIENT', 'PARTNER'),
    'support_request_status': ('OPEN', 'IN_PROGRESS', 'WAITING', 'RESOLVED', 'CLOSED'),
    'support_request_subject_type': ('ORDER', 'DOCUMENT', 'PAYOUT', 'SETTLEMENT', 'INTEGRATION', 'OTHER'),
    'usage_metric': ('CARDS_ACTIVE', 'TRANSACTIONS', 'ALERTS_SENT', 'EXPORTS'),
    'vehicle_engine_type': ('petrol', 'diesel', 'hybrid', 'electric'),
    'vehicle_mileage_source': ('FUEL_TXN', 'MANUAL_UPDATE', 'SERVICE_EVENT'),
    'vehicle_odometer_source': ('MANUAL', 'ESTIMATED', 'MIXED'),
    'vehicle_recommendation_status': ('ACTIVE', 'ACCEPTED', 'DONE', 'DISMISSED'),
    'vehicle_service_type': ('OIL_CHANGE', 'FILTERS', 'BRAKES', 'TIMING', 'OTHER'),
    'vehicle_usage_type': ('city', 'highway', 'mixed', 'aggressive'),
}

BI_ENUMS = {
    'bi_export_format': ('CSV', 'JSONL', 'PARQUET'),
    'bi_export_kind': ('ORDERS', 'ORDER_EVENTS', 'PAYOUTS', 'DECLINES', 'DAILY_METRICS'),
    'bi_export_scope_type': ('TENANT', 'CLIENT', 'PARTNER', 'STATION'),
    'bi_export_status': ('CREATED', 'GENERATED', 'DELIVERED', 'CONFIRMED', 'FAILED'),
    'bi_scope_type': ('TENANT', 'CLIENT', 'PARTNER', 'STATION'),
}


def _ensure_schema(schema: str) -> None:
    if not schema:
        return
    op.execute(sa.text(f'CREATE SCHEMA IF NOT EXISTS "{schema}"'))


def _create_enums(schema: str, enums: dict[str, tuple[str, ...]]) -> None:
    if not enums:
        return
    _ensure_schema(schema)
    bind = op.get_bind()
    for enum_name, values in sorted(enums.items()):
        ensure_pg_enum(bind, enum_name, values=values, schema=schema)


def upgrade() -> None:
    bind = op.get_bind()
    if not is_postgres(bind):
        return
    _create_enums(PROCESSING_SCHEMA, PROCESSING_ENUMS)
    _create_enums(BI_SCHEMA, BI_ENUMS)


def downgrade() -> None:
    # Downgrade intentionally left empty; enum removal is unsafe for shared types.
    pass

from app.models.invoice import InvoiceLine
from app.models.money_flow_v3 import MoneyFlowLinkNodeType, MoneyFlowLinkType
from app.services.money_flow.cfo_explain import summarize_invoice_lines
from app.services.money_flow.graph import MoneyFlowGraphBuilder
from app.services.money_flow.snapshots import evaluate_snapshot_invariants


def test_late_reversal_blocked_when_period_locked():
    payload = {"period": {"status": "LOCKED"}, "action": "REVERSAL"}
    violations = evaluate_snapshot_invariants(payload)
    assert "reversal_locked_period" in violations


def test_missing_ledger_posting_detected():
    payload = {"ledger": {"balanced": False}}
    violations = evaluate_snapshot_invariants(payload)
    assert "ledger_unbalanced" in violations


def test_double_apply_payment_idempotent():
    builder = MoneyFlowGraphBuilder(tenant_id=1, client_id="client-1")
    builder.add_link(
        src_type=MoneyFlowLinkNodeType.PAYMENT,
        src_id="payment-1",
        link_type=MoneyFlowLinkType.SETTLES,
        dst_type=MoneyFlowLinkNodeType.INVOICE,
        dst_id="invoice-1",
    )
    builder.add_link(
        src_type=MoneyFlowLinkNodeType.PAYMENT,
        src_id="payment-1",
        link_type=MoneyFlowLinkType.SETTLES,
        dst_type=MoneyFlowLinkNodeType.INVOICE,
        dst_id="invoice-1",
    )
    assert len(builder.build()) == 1


def test_subscription_proration_breakdown():
    lines = [
        InvoiceLine(invoice_id="invoice-1", product_id="subscription_base", line_amount=50000),
        InvoiceLine(invoice_id="invoice-1", product_id="subscription_proration", line_amount=10000),
    ]
    breakdown = summarize_invoice_lines(lines)
    assert breakdown.base_fee == 50000
    assert breakdown.overage == 10000

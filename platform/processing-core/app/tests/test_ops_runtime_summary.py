from app.services.ops_runtime import build_ops_summary


class _BrokenSession:
    def query(self, *args, **kwargs):
        raise RuntimeError("db unavailable")


def test_build_ops_summary_gracefully_degrades_on_metric_failures() -> None:
    payload = build_ops_summary(_BrokenSession())

    assert payload.core.health == "ok"
    assert payload.queues.exports.queued == 0
    assert payload.queues.emails.failed_1h == 0
    assert payload.billing.overdue_orgs == 0
    assert payload.reconciliation.parse_failed_24h == 0
    assert payload.warnings

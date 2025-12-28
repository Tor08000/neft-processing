from __future__ import annotations

import sys

import pytest


STABLE_SUITE = [
    "platform/processing-core/app/tests/test_billing_hardening_invariants.py",
    "platform/processing-core/app/tests/test_settlement_allocations.py",
    "platform/processing-core/app/tests/test_accounting_exports.py",
    "platform/processing-core/app/tests/test_documents_lifecycle.py",
    "platform/processing-core/app/tests/test_immutability_enforcement.py",
    "platform/processing-core/app/tests/test_risk_engine_v3.py",
    "platform/processing-core/app/tests/test_app_smoke.py",
    "platform/processing-core/app/tests/test_health.py",
]


def main() -> int:
    return pytest.main(STABLE_SUITE)


if __name__ == "__main__":
    sys.exit(main())

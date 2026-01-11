from __future__ import annotations

import os

import pytest


@pytest.mark.integration
def test_edo_sbis_e2e_send_delivered_signed() -> None:
    if os.getenv("EDO_E2E_ENABLED") != "1" or os.getenv("EDO_PROVIDER") != "SBIS":
        pytest.skip("EDO SBIS e2e disabled")
    required = [
        "SBIS_TEST_CREDENTIALS",
        "SBIS_TEST_WEBHOOK_SECRET",
    ]
    missing = [key for key in required if not os.getenv(key)]
    if missing:
        pytest.skip(f"Missing SBIS secrets: {', '.join(missing)}")
    pytest.skip("SBIS e2e requires live SBIS environment")

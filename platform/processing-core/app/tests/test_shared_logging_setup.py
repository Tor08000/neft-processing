from __future__ import annotations

import json
import logging
from uuid import uuid4

from neft_shared.logging_setup import _json_formatter


def test_json_formatter_serializes_uuid_extras() -> None:
    invoice_id = uuid4()
    record = logging.LogRecord(
        name="test",
        level=logging.INFO,
        pathname=__file__,
        lineno=1,
        msg="invoice_replay",
        args=(),
        exc_info=None,
    )
    record.invoice_id = invoice_id

    payload = json.loads(_json_formatter(record))

    assert payload["msg"] == "invoice_replay"
    assert payload["invoice_id"] == str(invoice_id)

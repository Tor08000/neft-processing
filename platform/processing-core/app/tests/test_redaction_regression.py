from app.services.case_event_redaction import REDACTION_DISPLAY, redact_deep


def test_redaction_masks_email_phone_and_token() -> None:
    payload = {
        "email": "alice@example.com",
        "phone": "+7 999 123-45-67",
        "token": "secret-token",
        "nested": {"contact_email": "bob@example.com", "meta": "bearer abc.def.ghi"},
    }
    redacted = redact_deep(payload, "", include_hash=False)
    assert redacted["email"] != payload["email"]
    assert redacted["phone"] != payload["phone"]
    assert redacted["token"]["redacted"] is True
    assert redacted["token"]["display"] == REDACTION_DISPLAY
    assert redacted["nested"]["contact_email"] != payload["nested"]["contact_email"]
    assert redacted["nested"]["meta"]["redacted"] is True
    assert REDACTION_DISPLAY in redacted["nested"]["meta"]["display"]

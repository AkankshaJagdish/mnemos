from backend.services.memory_service import redact_pii


def test_redact_pii_replaces_email_and_phone():
    value = redact_pii("Email jane.doe@example.com and call +1 (415) 555-0132. Date: 2026-10-26.")
    assert "jane.doe@example.com" not in value
    assert "415" not in value
    assert "[REDACTED_EMAIL]" in value
    assert "[REDACTED_PHONE]" in value
    # A date is not treated as a phone number.
    assert "2026-10-26" in value


def test_redact_pii_leaves_text_without_contact_details_unchanged():
    assert redact_pii("I prefer concise answers and Python examples.") == "I prefer concise answers and Python examples."

# tests/test_redact.py
from itkb.ingestion.redact import redact_pii


def test_redacts_email_direct():
    assert "mail: [EMAIL REDACTED]" in redact_pii("mail: foo@bar.com")


def test_redacts_email_not_present_when_absent():
    assert redact_pii("no personal data here") == "no personal data here"


def test_redacts_phone():
    assert "[PHONE REDACTED]" in redact_pii("call +1 (555) 123-4567 now")


def test_redacts_ssn():
    assert "[NATIONAL_ID REDACTED]" in redact_pii("ssn 123-45-6789")


def test_redacts_credit_card():
    assert "[CREDIT_CARD REDACTED]" in redact_pii("card 4111 1111 1111 1111")


def test_keeps_ip_addresses():
    text = "server at 192.168.1.10 and 10.0.0.1"
    assert redact_pii(text) == text


def test_keeps_hostnames_and_tokens():
    text = "ssh server01.example.com; token sk-abc123xyz456"
    assert redact_pii(text) == text


def test_keeps_version_numbers():
    text = "nginx version 1.2.3 and kernel 6.1.0"
    assert redact_pii(text) == text

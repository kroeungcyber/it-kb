# itkb/ingestion/redact.py
from __future__ import annotations
import re

_RULES = [
    (re.compile(r"\b[\w.+-]+@[\w-]+\.[\w.]+\b"), "[EMAIL REDACTED]"),
    (re.compile(r"\b(?:\d[ -]?){13,19}\b"), "[CREDIT_CARD REDACTED]"),
    (re.compile(r"(?<!\d)(?:\+?\d{1,3}[-.\s]?)?\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}(?!\d)"),
     "[PHONE REDACTED]"),
    (re.compile(r"\b\d{3}-\d{2}-\d{4}\b"), "[NATIONAL_ID REDACTED]"),
    (re.compile(r"\b\d{9}\b"), "[NATIONAL_ID REDACTED]"),
]


def redact_pii(text: str) -> str:
    for pattern, marker in _RULES:
        text = pattern.sub(marker, text)
    return text

import re

from app.guardrails.base import GuardrailBlocked, GuardrailEvent
from app.schemas import Message

EMAIL = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")
CARD = re.compile(r"(?<!\d)(?:\d[ -]?){13,16}(?!\d)")
AADHAAR = re.compile(r"(?<!\d)\d{4}[ -]\d{4}[ -]\d{4}(?!\d)")
PAN = re.compile(r"\b[A-Z]{5}\d{4}[A-Z]\b")
PHONE = re.compile(r"(?<!\d)(?:\+\d{1,3}[ -]?)?(?:[6-9]\d{9}|\d{3}[ -]\d{3}[ -]\d{4})(?!\d)")


def _luhn(num: str) -> bool:
    total = 0
    for i, ch in enumerate(reversed(num)):
        d = int(ch)
        if i % 2 == 1:
            d *= 2
            if d > 9:
                d -= 9
        total += d
    return total % 10 == 0


def _card_repl(m: re.Match) -> str:
    digits = re.sub(r"\D", "", m.group())
    if 13 <= len(digits) <= 16 and _luhn(digits):
        return "[CARD]"
    return m.group()  # random digits that fail Luhn are left alone


def redact_text(text: str) -> tuple[str, dict]:
    found: dict[str, int] = {}

    def apply(pattern, label, fn=None):
        nonlocal text

        def repl(m):
            out = fn(m) if fn else f"[{label}]"
            if out != m.group():
                found[label] = found.get(label, 0) + 1
            return out

        text = pattern.sub(repl, text)

    # order matters: specific patterns first, phone last
    apply(EMAIL, "EMAIL")
    apply(CARD, "CARD", _card_repl)
    apply(AADHAAR, "AADHAAR")
    apply(PAN, "PAN")
    apply(PHONE, "PHONE")
    return text, found


def check_pii(messages: list[Message], mode: str):
    if mode == "off":
        return messages, []

    new_messages, events = [], []
    for m in messages:
        if m.role != "user":
            new_messages.append(m)
            continue
        text, found = redact_text(m.content)
        if found:
            ev = GuardrailEvent(
                "pii", "block" if mode == "block" else "redact", f"found: {found}"
            )
            if mode == "block":
                raise GuardrailBlocked(ev)
            events.append(ev)
        new_messages.append(Message(role=m.role, content=text))
    return new_messages, events
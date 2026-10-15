import re

from app.guardrails.base import GuardrailBlocked, GuardrailEvent
from app.schemas import Message

_RAW = [
    r"ignore\s+(?:all\s+|any\s+|the\s+)?(?:previous|prior|above|earlier)\s+(?:instructions|prompts?|rules)",
    r"disregard\s+(?:all\s+|any\s+|the\s+)?(?:previous|prior|above|earlier)\s+(?:instructions|prompts?|rules)",
    r"forget\s+(?:everything|all)\s+(?:you|above|previous)",
    r"(?:reveal|show|print|repeat)\s+(?:me\s+)?(?:your|the)\s+(?:system|hidden|initial)\s+(?:prompt|instructions)",
    r"you\s+are\s+now\s+(?:in\s+)?(?:dan|developer\s+mode|jailbreak)",
    r"\bjailbreak\b",
    r"\bdeveloper\s+mode\b",
]
PATTERNS = [re.compile(p, re.IGNORECASE) for p in _RAW]


def check_injection(messages: list[Message], mode: str):
    if mode == "off":
        return messages, []

    events = []
    for m in messages:
        if m.role != "user":
            continue
        for p in PATTERNS:
            if p.search(m.content):
                ev = GuardrailEvent(
                    "injection",
                    "block" if mode == "block" else "flag",
                    f"matched pattern: {p.pattern[:50]}",
                )
                if mode == "block":
                    raise GuardrailBlocked(ev)
                events.append(ev)
                break
    return messages, events
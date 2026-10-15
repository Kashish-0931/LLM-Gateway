from dataclasses import dataclass


@dataclass
class GuardrailEvent:
    guardrail: str  # "length" | "pii" | "injection"
    action: str     # "redact" | "block" | "flag"
    detail: str


class GuardrailBlocked(Exception):
    def __init__(self, event: GuardrailEvent):
        self.event = event
        super().__init__(event.detail)
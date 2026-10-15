from app.guardrails.base import GuardrailBlocked, GuardrailEvent
from app.schemas import Message


def check_length(messages: list[Message], max_chars: int):
    total = sum(len(m.content) for m in messages)
    if total > max_chars:
        raise GuardrailBlocked(
            GuardrailEvent("length", "block", f"input is {total} chars, limit is {max_chars}")
        )
    return messages, []
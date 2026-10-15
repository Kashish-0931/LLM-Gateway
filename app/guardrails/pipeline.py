from pathlib import Path

import yaml

from app.guardrails.injection import check_injection
from app.guardrails.length import check_length
from app.guardrails.pii import check_pii
from app.schemas import Message

CONFIG_FILE = Path(__file__).resolve().parent.parent.parent / "config" / "gateway.yaml"

DEFAULTS = {"max_chars": 8000, "pii": "redact", "injection": "block"}


def load_cfg() -> dict:
    data = yaml.safe_load(CONFIG_FILE.read_text(encoding="utf-8")) or {}
    return {**DEFAULTS, **(data.get("guardrails", {}).get("input", {}) or {})}


CFG = load_cfg()


def run_input_guardrails(messages: list[Message], cfg: dict | None = None):
    """Returns (clean_messages, events). Raises GuardrailBlocked on a block."""
    cfg = cfg or CFG
    events = []

    messages, ev = check_length(messages, cfg["max_chars"])
    events += ev
    messages, ev = check_injection(messages, cfg["injection"])
    events += ev
    messages, ev = check_pii(messages, cfg["pii"])
    events += ev

    return messages, events
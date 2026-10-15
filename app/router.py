import re
from dataclasses import dataclass, field

from app.schemas import ChatRequest

HARD_WORDS = re.compile(
    r"\b(prove|derive|analy[sz]e|compare|design|architecture|refactor|debug|"
    r"optimi[sz]e|algorithm|implement|trade-?offs?|step[- ]by[- ]step)\b",
    re.I,
)
CODE_HINT = re.compile(
    r"```|\bdef \w+\(|\bclass \w+|\bSELECT\b.*\bFROM\b|\bimport \w+", re.I | re.S
)

HARD_THRESHOLD = 3
EASY_CHAIN = "fast"
HARD_CHAIN = "smart"


@dataclass
class RouteDecision:
    chain: str
    score: int
    reasons: list[str] = field(default_factory=list)


def classify(req: ChatRequest) -> RouteDecision:
    text = "\n".join(m.content for m in req.messages if m.role == "user")
    score, reasons = 0, []

    if len(text) > 800:
        score += 2
        reasons.append("long_prompt")
    elif len(text) > 300:
        score += 1
        reasons.append("medium_prompt")

    if CODE_HINT.search(text):
        score += 2
        reasons.append("code")

    hits = len(HARD_WORDS.findall(text))
    if hits:
        score += min(hits, 2)
        reasons.append(f"hard_keywords:{hits}")

    if text.count("?") >= 2:
        score += 1
        reasons.append("multi_question")

    if len(req.messages) > 6:
        score += 1
        reasons.append("long_conversation")

    if req.max_tokens > 1000:
        score += 1
        reasons.append("large_output")

    chain = HARD_CHAIN if score >= HARD_THRESHOLD else EASY_CHAIN
    return RouteDecision(chain, score, reasons)
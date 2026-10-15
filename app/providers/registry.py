from pathlib import Path

import yaml

from app.config import settings
from app.providers.openai_compat import OpenAICompatProvider
from app.schemas import Target

CONFIG_FILE = Path(__file__).resolve().parent.parent.parent / "config" / "gateway.yaml"

_cfg = yaml.safe_load(CONFIG_FILE.read_text(encoding="utf-8"))

# provider name -> provider object (built from the yaml)
PROVIDERS = {
    name: OpenAICompatProvider(
        name,
        p["base_url"],
        getattr(settings, p["api_key_env"].lower(), ""),  # HF_TOKEN -> settings.hf_token
    )
    for name, p in _cfg["providers"].items()
}

# alias -> list of targets
CHAINS: dict[str, list[Target]] = {
    alias: [Target(**t) for t in targets]
    for alias, targets in (_cfg.get("chains") or {}).items()
}

DEFAULT_PROVIDER = next(iter(PROVIDERS))  # first provider in the yaml
import sys
from contextlib import contextmanager

from app.config import settings

_client = None

if settings.langfuse_public_key and settings.langfuse_secret_key:
    try:
        from langfuse import Langfuse

        _client = Langfuse(
            public_key=settings.langfuse_public_key,
            secret_key=settings.langfuse_secret_key,
            base_url=settings.langfuse_base_url,
        )
    except Exception as e:
        print(f"[langfuse] init failed: {e}")


class _Obs:
    """Wraps a Langfuse observation; update() can never raise."""

    def __init__(self, obs=None):
        self._obs = obs

    def update(self, **kwargs):
        if self._obs is None:
            return
        try:
            self._obs.update(**kwargs)
        except Exception as e:
            print(f"[langfuse] update failed: {e}")


@contextmanager
def observation(name: str, as_type: str = "span", **kwargs):
    """Open a Langfuse span/generation/guardrail. Never breaks the request."""
    if _client is None:
        yield _Obs()
        return

    try:
        cm = _client.start_as_current_observation(as_type=as_type, name=name, **kwargs)
        obs = cm.__enter__()
    except Exception as e:
        print(f"[langfuse] start failed: {e}")
        yield _Obs()
        return

    try:
        yield _Obs(obs)
    except BaseException:
        try:
            cm.__exit__(*sys.exc_info())
        except Exception:
            pass
        raise
    else:
        try:
            cm.__exit__(None, None, None)
        except Exception:
            pass


def flush():
    if _client is not None:
        try:
            _client.flush()
        except Exception as e:
            print(f"[langfuse] flush failed: {e}")
import time


class CircuitBreaker:
    """After `threshold` failures, skip a target for `cooldown` seconds."""

    def __init__(self, threshold: int = 3, cooldown: float = 30):
        self.threshold = threshold
        self.cooldown = cooldown
        self.failures: dict[str, int] = {}
        self.opened_at: dict[str, float] = {}

    def is_open(self, key: str) -> bool:
        t = self.opened_at.get(key)
        if t is None:
            return False
        if time.monotonic() - t >= self.cooldown:
            # half-open: allow one trial; one more failure re-opens it
            del self.opened_at[key]
            self.failures[key] = self.threshold - 1
            return False
        return True

    def record_success(self, key: str):
        self.failures.pop(key, None)
        self.opened_at.pop(key, None)

    def record_failure(self, key: str):
        n = self.failures.get(key, 0) + 1
        self.failures[key] = n
        if n >= self.threshold:
            self.opened_at[key] = time.monotonic()
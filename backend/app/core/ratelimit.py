from __future__ import annotations

import threading
import time
from collections import defaultdict, deque


class SlidingWindowLimiter:
    """Small in-process limiter for login attempts.

    A prototype runs one API process; for a multi-worker deployment this moves
    to Redis without changing the call sites.
    """

    def __init__(self, limit: int, window_seconds: int) -> None:
        self.limit = max(1, limit)
        self.window = max(1, window_seconds)
        self._hits: dict[str, deque[float]] = defaultdict(deque)
        self._lock = threading.Lock()

    def allow(self, key: str) -> tuple[bool, int]:
        """Return (allowed, retry_after_seconds)."""
        now = time.monotonic()
        with self._lock:
            window = self._hits[key]
            while window and now - window[0] > self.window:
                window.popleft()
            if len(window) >= self.limit:
                retry = int(self.window - (now - window[0])) + 1
                return False, retry
            window.append(now)
            return True, 0

    def reset(self, key: str | None = None) -> None:
        with self._lock:
            if key is None:
                self._hits.clear()
            else:
                self._hits.pop(key, None)

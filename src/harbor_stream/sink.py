"""Thread-backed HTTP event sink."""

from __future__ import annotations

import json
import queue
import threading
import time
import urllib.error
import urllib.request


class EventSink:
    """Serialize event delivery behind a worker thread."""

    def __init__(
        self,
        *,
        url: str,
        token: str | None,
        timeout: float = 5.0,
        max_retries: int = 3,
    ):
        self._url = url
        self._token = token
        self._timeout = timeout
        self._max_retries = max_retries
        self._queue: queue.Queue[dict | None] = queue.Queue()
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._started = False

    def start(self) -> None:
        if not self._started:
            self._thread.start()
            self._started = True

    def emit(self, event: dict) -> None:
        if not self._started:
            self.start()
        self._queue.put(event)

    def close(self) -> None:
        if not self._started:
            return
        self._queue.put(None)
        self._thread.join(timeout=15.0)

    def _run(self) -> None:
        while True:
            item = self._queue.get()
            if item is None:
                return
            self._post_with_retries(item)

    def _post_with_retries(self, event: dict) -> None:
        body = json.dumps(event, ensure_ascii=False).encode()
        headers = {"Content-Type": "application/json"}
        if self._token:
            headers["Authorization"] = f"Bearer {self._token}"

        last_error: Exception | None = None
        for attempt in range(self._max_retries):
            req = urllib.request.Request(self._url, data=body, headers=headers, method="POST")
            try:
                with urllib.request.urlopen(req, timeout=self._timeout) as resp:
                    if 200 <= resp.status < 300:
                        return
                    raise RuntimeError(f"unexpected HTTP status {resp.status}")
            except (urllib.error.URLError, OSError, RuntimeError) as exc:
                last_error = exc
                time.sleep(min(0.5 * (attempt + 1), 2.0))

        if last_error is not None:
            print(f"[harbor-stream] failed to POST event: {last_error}")

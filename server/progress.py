"""Capture stdout and logging output for real-time SSE streaming."""

import io
import logging
import sys
import threading
import time


class ProgressCapture:
    """Context manager that captures stdout + log output into a thread-safe list.

    Usage:
        cap = ProgressCapture()
        with cap:
            print("hello")        # captured
            log.info("working")   # captured
        lines = cap.lines         # ["hello", "  → working"]
    """

    def __init__(self):
        self.lines: list[str] = []
        self._lock = threading.Lock()
        self._old_stdout = None
        self._handler = None

    def _add_line(self, text: str):
        with self._lock:
            self.lines.append(text)

    def __enter__(self):
        # Capture stdout
        self._old_stdout = sys.stdout
        sys.stdout = _CaptureStream(self._add_line, self._old_stdout)

        # Capture logging (root logger)
        self._handler = _CaptureHandler(self._add_line)
        logging.root.addHandler(self._handler)
        return self

    def __exit__(self, *exc):
        sys.stdout = self._old_stdout
        logging.root.removeHandler(self._handler)


class _CaptureStream(io.TextIOBase):
    """Replacement stdout that copies lines to a callback."""

    def __init__(self, callback, passthrough):
        self._callback = callback
        self._passthrough = passthrough
        self._buffer = ""

    def write(self, s: str) -> int:
        if self._passthrough:
            self._passthrough.write(s)
        self._buffer += s
        while "\n" in self._buffer:
            line, self._buffer = self._buffer.split("\n", 1)
            stripped = line.rstrip()
            if stripped:
                self._callback(stripped)
        return len(s)

    def flush(self):
        if self._passthrough:
            self._passthrough.flush()
        if self._buffer.strip():
            self._callback(self._buffer.strip())
            self._buffer = ""


class _CaptureHandler(logging.Handler):
    """Logging handler that feeds formatted records to a callback."""

    def __init__(self, callback):
        super().__init__(level=logging.DEBUG)
        self._callback = callback

    def emit(self, record):
        try:
            msg = self.format(record) or record.getMessage()
            if msg.strip():
                self._callback(msg.strip())
        except Exception:
            pass

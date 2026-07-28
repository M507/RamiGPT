"""Tests for optional global AI request queuing."""

from __future__ import annotations

import threading
import time
import unittest
from typing import Dict, List
from unittest.mock import patch

from ramigpt.ai.base import AIProvider, ChatMessage
from ramigpt.ai.request_queue import QueuedAIProvider, ai_request_queue_lock
from ramigpt.config.settings import Settings, _apply_updates


class _SlowProvider(AIProvider):
    name = "slow"

    def __init__(self) -> None:
        self.calls: List[int] = []
        self._lock = threading.Lock()
        self._counter = 0

    def create_completion(self, messages: List[ChatMessage]) -> str:
        with self._lock:
            self._counter += 1
            call_id = self._counter
        time.sleep(0.05)
        with self._lock:
            self.calls.append(call_id)
        return "ok"


class AIRequestQueueSettingsTests(unittest.TestCase):
    def test_apply_updates_coerces_toggle(self) -> None:
        updated = _apply_updates(Settings(), {"ai_request_queue": True})
        self.assertEqual(updated.ai_request_queue, 1)
        updated = _apply_updates(Settings(), {"ai_request_queue": 0})
        self.assertEqual(updated.ai_request_queue, 0)


class AIRequestQueueLockTests(unittest.TestCase):
    def test_lock_serializes_when_enabled(self) -> None:
        inner = _SlowProvider()
        provider = QueuedAIProvider(inner)
        overlap = threading.Event()
        done = threading.Event()

        def worker() -> None:
            with patch(
                "ramigpt.ai.request_queue.ai_request_queue_enabled",
                return_value=True,
            ):
                provider.create_completion([{"role": "user", "content": "hi"}])
            if not overlap.is_set():
                overlap.set()
            done.set()

        threads = [threading.Thread(target=worker) for _ in range(3)]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join(timeout=2)
        self.assertTrue(done.wait(timeout=0.1))
        self.assertEqual(inner.calls, [1, 2, 3])

    def test_lock_noop_when_disabled(self) -> None:
        started = threading.Barrier(2)
        release = threading.Event()

        def hold_lock() -> None:
            with patch(
                "ramigpt.ai.request_queue.ai_request_queue_enabled",
                return_value=True,
            ):
                with ai_request_queue_lock():
                    started.wait(timeout=1)
                    release.wait(timeout=1)

        holder = threading.Thread(target=hold_lock)
        holder.start()
        started.wait(timeout=1)

        with patch(
            "ramigpt.ai.request_queue.ai_request_queue_enabled",
            return_value=False,
        ):
            entered = threading.Event()

            def try_enter() -> None:
                with ai_request_queue_lock():
                    entered.set()

            other = threading.Thread(target=try_enter)
            other.start()
            other.join(timeout=1)
            self.assertTrue(entered.is_set())

        release.set()
        holder.join(timeout=1)


class QueuedAIProviderTests(unittest.TestCase):
    def test_forwards_name_and_usage(self) -> None:
        class FakeInner(AIProvider):
            name = "fake"
            last_usage: Dict[str, int] = {"prompt_tokens": 1}

            def create_completion(self, messages: List[ChatMessage]) -> str:
                return "reply"

        wrapped = QueuedAIProvider(FakeInner())
        self.assertEqual(wrapped.name, "fake")
        self.assertEqual(
            wrapped.create_completion([{"role": "user", "content": "x"}]),
            "reply",
        )
        self.assertEqual(wrapped.last_usage, {"prompt_tokens": 1})


if __name__ == "__main__":
    unittest.main()

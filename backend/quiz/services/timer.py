"""In-process timers for question phase auto-submit and auto-advance."""
from __future__ import annotations

import logging
import threading
from typing import Callable

logger = logging.getLogger(__name__)


class TimerService:
    def __init__(self) -> None:
        self._timers: dict[tuple[int, int], threading.Timer] = {}
        self._lock = threading.Lock()

    def schedule(self, session_id: int, question_index: int, delay_seconds: float, callback: Callable[[], None]) -> None:
        key = (session_id, question_index)

        def run():
            from django.db import close_old_connections

            close_old_connections()
            try:
                callback()
            except Exception:
                logger.exception("Timer callback failed session=%s q=%s", session_id, question_index)
            finally:
                with self._lock:
                    self._timers.pop(key, None)

        with self._lock:
            self._cancel_timeout_timer(session_id, question_index)
            timer = threading.Timer(delay_seconds, run)
            timer.daemon = True
            self._timers[key] = timer
            timer.start()

    def _cancel_timeout_timer(self, session_id: int, question_index: int) -> None:
        key = (session_id, question_index)
        with self._lock:
            timer = self._timers.pop(key, None)
        if timer:
            timer.cancel()

    def cancel(self, session_id: int, question_index: int) -> None:
        self._cancel_timeout_timer(session_id, question_index)

    def cancel_all(self) -> None:
        with self._lock:
            timers = list(self._timers.values())
            self._timers.clear()
        for timer in timers:
            timer.cancel()


timer_service = TimerService()


class AdvanceScheduler:
    """排程 session 在指定 delay 後呼叫 on_fire()。

    一個 session 同時只允許一個 pending advance。當 next_question() 觸發或
    session 進入 review/closed 時應呼叫 cancel(session_id)。
    """

    def __init__(self) -> None:
        self._timers: dict[int, threading.Timer] = {}
        self._lock = threading.Lock()

    def schedule(self, session_id: int, delay_seconds: float, on_fire: Callable[[], None]) -> None:
        def run():
            from django.db import close_old_connections

            close_old_connections()
            with self._lock:
                self._timers.pop(session_id, None)
            try:
                on_fire()
            except Exception:
                logger.exception("Advance scheduler callback failed session=%s", session_id)

        with self._lock:
            self._cancel_locked(session_id)
            timer = threading.Timer(delay_seconds, run)
            timer.daemon = True
            self._timers[session_id] = timer
            timer.start()

    def _cancel_locked(self, session_id: int) -> None:
        timer = self._timers.pop(session_id, None)
        if timer:
            timer.cancel()

    def cancel(self, session_id: int) -> None:
        with self._lock:
            self._cancel_locked(session_id)

    def cancel_all(self) -> None:
        with self._lock:
            sessions = list(self._timers.keys())
            self._timers.clear()
        for sid in sessions:
            with self._lock:
                self._cancel_locked(sid)

    def is_pending(self, session_id: int) -> bool:
        with self._lock:
            return session_id in self._timers


advance_scheduler = AdvanceScheduler()

_session_mutexes: dict[int, threading.Lock] = {}
_meta_lock = threading.Lock()


def session_mutex(session_id: int) -> threading.Lock:
    """同一場次同一時間只允許一個執行緒修改狀態（避免計時 callback 與 API 搶 SQLite 鎖）。"""
    with _meta_lock:
        lock = _session_mutexes.get(session_id)
        if lock is None:
            lock = threading.Lock()
            _session_mutexes[session_id] = lock
        return lock

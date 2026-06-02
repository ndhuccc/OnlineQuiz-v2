"""Quiz session state machine and broadcasts."""
from __future__ import annotations

import threading
import time
from datetime import timedelta

from django.db import close_old_connections, transaction
from django.utils import timezone

from quiz.models import Answer, Participant, Question, QuestionBank, QuizSession, generate_join_code, generate_token
from quiz.services.answers import finalize_question_answers
from quiz.services.broadcast import broadcast_after_commit
from quiz.services.stats import question_stats_payload, session_summary_payload
from quiz.services.timer import session_mutex, timer_service


class SessionError(Exception):
    pass


_schedule_epoch = 0
_schedule_lock = threading.Lock()


def invalidate_pending_schedules() -> None:
    """取消尚未啟動的背景排程與已啟動的計時器。"""
    global _schedule_epoch
    with _schedule_lock:
        _schedule_epoch += 1
    timer_service.cancel_all()


def _unique_join_code() -> str:
    for _ in range(20):
        code = generate_join_code()
        if not QuizSession.objects.filter(join_code=code).exists():
            return code
    raise SessionError("無法產生加入代碼")


@transaction.atomic
def create_session(bank_id: int) -> QuizSession:
    bank = QuestionBank.objects.get(pk=bank_id)
    question_ids = list(bank.questions.order_by("order_index").values_list("id", flat=True))
    if not question_ids:
        raise SessionError("題庫沒有題目")

    session = QuizSession.objects.create(
        bank=bank,
        join_code=_unique_join_code(),
        host_token=generate_token(32),
        question_snapshot=question_ids,
        status=QuizSession.Status.LOBBY,
        current_question_index=0,
        current_phase=QuizSession.Phase.STEM,
    )
    return session


def _clear_phase_timer(session: QuizSession) -> None:
    session.phase_started_at = None
    session.phase_timer_seconds = None
    session.phase_ends_at = None


def compute_phase_remaining_seconds(session: QuizSession, now=None) -> int | None:
    """後端計算 options 階段剩餘秒數（供輪詢同步）。"""
    if session.current_phase != QuizSession.Phase.OPTIONS:
        return None
    if session.phase_ends_at is None:
        return None
    if now is None:
        now = timezone.now()
    return max(0, int((session.phase_ends_at - now).total_seconds()))


def _start_options_timer(session: QuizSession, seconds: int):
    """教師按下 Open Options & Start Timer 時寫入本題開始時間。"""
    now = timezone.now()
    session.phase_started_at = now
    session.phase_timer_seconds = seconds
    session.phase_ends_at = now + timedelta(seconds=seconds)
    return session.phase_ends_at


def _update_options_timer_duration(session: QuizSession, seconds: int):
    """調整倒數秒數；保留原 phase_started_at。"""
    if not session.phase_started_at:
        return _start_options_timer(session, seconds)
    session.phase_timer_seconds = seconds
    session.phase_ends_at = session.phase_started_at + timedelta(seconds=seconds)
    return session.phase_ends_at


def public_base_url() -> str:
    from django.conf import settings

    from quiz.services.network import resolve_base_url

    return resolve_base_url(
        configured=getattr(settings, "LAN_BASE_URL", ""),
        port=getattr(settings, "APP_PORT", 3080),
    )


def join_url_for_session(session: QuizSession) -> str:
    return f"{public_base_url()}/student/quiz?code={session.join_code}"


def session_state_payload(session: QuizSession) -> dict:
    q = session.current_question()
    remaining = compute_phase_remaining_seconds(session)
    return {
        "session_id": session.id,
        "join_code": session.join_code,
        "join_url": join_url_for_session(session),
        "status": session.status,
        "current_question_index": session.current_question_index,
        "current_phase": session.current_phase,
        "phase_started_at": session.phase_started_at.isoformat() if session.phase_started_at else None,
        "phase_timer_seconds": session.phase_timer_seconds,
        "phase_remaining_seconds": remaining,
        "total_questions": len(session.question_ids),
        "current_question_id": q.id if q else None,
    }


def question_meta_payload(session: QuizSession) -> dict | None:
    """學生端可見的題目資訊（不含題幹）。"""
    q = session.current_question()
    if not q:
        return None
    return {
        "question_index": session.current_question_index,
        "type": q.type,
        "timer_seconds": q.timer_seconds,
        "points": str(q.points),
    }


def stem_payload(session: QuizSession) -> dict | None:
    q = session.current_question()
    if not q:
        return None
    return {
        "question_index": session.current_question_index,
        "stem_text": q.stem_text,
        "type": q.type,
        "category": q.category,
        "points": str(q.points),
        "timer_seconds": q.timer_seconds,
    }


def push_question_stats(session: QuizSession) -> None:
    question = session.current_question()
    if not question:
        return
    sid = session.id
    payload = question_stats_payload(session, question)
    broadcast_after_commit(sid, "session:question_stats", payload)


def _emit_phase(session: QuizSession) -> None:
    sid = session.id
    broadcast_after_commit(sid, "session:phase_changed", session_state_payload(session))


def _emit_phase_deferred(session: QuizSession) -> None:
    """HTTP 回應後再廣播，避免 Daphne 在 transaction/on_commit 內卡住。"""

    sid = session.id

    def work():
        close_old_connections()
        time.sleep(0.05)
        try:
            from quiz.services.broadcast import broadcast

            current = QuizSession.objects.get(pk=sid)
            broadcast(sid, "session:phase_changed", session_state_payload(current))
        except QuizSession.DoesNotExist:
            return

    threading.Thread(target=work, daemon=True, name=f"quiz-emit-phase-{sid}").start()


def _cancel_timer(session: QuizSession) -> None:
    timer_service.cancel(session.id, session.current_question_index)


def _schedule_timeout(session_id: int, question_index: int, ends_at) -> None:
    delay = (ends_at - timezone.now()).total_seconds()
    if delay <= 0:

        def fire_now():
            handle_phase_timeout(session_id, question_index)

        threading.Thread(target=fire_now, daemon=True, name="quiz-phase-timeout").start()
        return

    def on_timeout():
        handle_phase_timeout(session_id, question_index)

    timer_service.schedule(session_id, question_index, delay, on_timeout)


def _schedule_timeout_after_request(session_id: int, question_index: int, ends_at) -> None:
    """HTTP 回應後再排程逾時，避免與進行中的 API 請求搶 SQLite 鎖。"""

    with _schedule_lock:
        epoch = _schedule_epoch

    def work():
        time.sleep(0.25)
        with _schedule_lock:
            if epoch != _schedule_epoch:
                return
        close_old_connections()
        _schedule_timeout(session_id, question_index, ends_at)

    threading.Thread(target=work, daemon=True, name="quiz-schedule-timeout").start()


def _close_options_phase(session: QuizSession, question: Question) -> None:
    """結束本題 options 階段（逾時、全員提交或手動縮時至 0）。"""
    finalize_question_answers(session, question)
    session.current_phase = QuizSession.Phase.CLOSED
    _clear_phase_timer(session)
    session.save(
        update_fields=["current_phase", "phase_started_at", "phase_timer_seconds", "phase_ends_at"]
    )
    timer_service.cancel(session.id, session.current_question_index)
    push_question_stats(session)
    _emit_phase_deferred(session)


def try_close_options_if_all_answered(session: QuizSession, question: Question) -> bool:
    """若全部參與者皆已提交，提前結束本題作答。"""
    sid = session.id
    q_index = session.current_question_index
    with session_mutex(sid):
        with transaction.atomic():
            session.refresh_from_db()
            if session.current_phase != QuizSession.Phase.OPTIONS:
                return False
            if session.current_question_index != q_index:
                return False
            current = session.current_question()
            if not current or current.id != question.id:
                return False
            total = session.participants.count()
            if total == 0:
                return False
            submitted = Answer.objects.filter(session=session, question=question).count()
            if submitted < total:
                return False
            _close_options_phase(session, question)
            return True
    return False


def handle_phase_timeout(session_id: int, question_index: int) -> None:
    close_old_connections()
    with session_mutex(session_id):
        with transaction.atomic():
            _handle_phase_timeout_locked(session_id, question_index)


def _handle_phase_timeout_locked(session_id: int, question_index: int) -> None:
    session = QuizSession.objects.get(pk=session_id)
    if session.status != QuizSession.Status.RUNNING:
        return
    if session.current_question_index != question_index:
        return
    if session.current_phase != QuizSession.Phase.OPTIONS:
        return

    question = session.current_question()
    if not question:
        return

    _close_options_phase(session, question)


def adjust_timer(session: QuizSession, timer_seconds: int) -> QuizSession:
    sid = session.id
    with session_mutex(sid):
        with transaction.atomic():
            _adjust_timer_locked(session, timer_seconds)
            session.refresh_from_db()
    return session


@transaction.atomic
def start_session(session: QuizSession) -> QuizSession:
    if session.status != QuizSession.Status.LOBBY:
        raise SessionError("僅大廳狀態可開始測驗")
    session.status = QuizSession.Status.RUNNING
    session.started_at = timezone.now()
    session.current_question_index = 0
    # Directly open options for the first question with its timer
    question = session.current_question()
    if question:
        _start_options_timer(session, question.timer_seconds)
        session.current_phase = QuizSession.Phase.OPTIONS
    else:
        session.current_phase = QuizSession.Phase.STEM
        _clear_phase_timer(session)
    session.save(
        update_fields=[
            "status",
            "started_at",
            "current_question_index",
            "current_phase",
            "phase_started_at",
            "phase_timer_seconds",
            "phase_ends_at",
        ]
    )
    broadcast_after_commit(session.id, "session:started", session_state_payload(session))
    _emit_phase(session)
    return session


def set_phase(
    session: QuizSession,
    phase: str,
    timer_seconds: int | None = None,
) -> QuizSession:
    sid = session.id
    with session_mutex(sid):
        with transaction.atomic():
            _set_phase_locked(session, phase, timer_seconds)
            session.refresh_from_db()
    return session


def _set_phase_locked(
    session: QuizSession,
    phase: str,
    timer_seconds: int | None = None,
) -> None:
    if session.status != QuizSession.Status.RUNNING:
        raise SessionError("測驗尚未開始")

    _cancel_timer(session)

    if phase == QuizSession.Phase.OPTIONS:
        question = session.current_question()
        if not question:
            raise SessionError("沒有進行中的題目")
        seconds = timer_seconds if timer_seconds is not None else question.timer_seconds
        _start_options_timer(session, seconds)
        session.current_phase = QuizSession.Phase.OPTIONS
        session.save(
            update_fields=[
                "current_phase",
                "phase_started_at",
                "phase_timer_seconds",
                "phase_ends_at",
            ]
        )
    elif phase == QuizSession.Phase.CLOSED:
        question = session.current_question()
        if question:
            finalize_question_answers(session, question)
        session.current_phase = QuizSession.Phase.CLOSED
        _clear_phase_timer(session)
        session.save(
            update_fields=["current_phase", "phase_started_at", "phase_timer_seconds", "phase_ends_at"]
        )
        push_question_stats(session)
    elif phase == QuizSession.Phase.STEM:
        session.current_phase = QuizSession.Phase.STEM
        _clear_phase_timer(session)
        session.save(
            update_fields=["current_phase", "phase_started_at", "phase_timer_seconds", "phase_ends_at"]
        )
    else:
        raise SessionError(f"不支援的階段：{phase}")


def _adjust_timer_locked(session: QuizSession, timer_seconds: int) -> None:
    if session.current_phase != QuizSession.Phase.OPTIONS:
        raise SessionError("僅選項作答階段可調整計時")
    if timer_seconds == 0:
        raise SessionError("秒數不可為 0")

    question = session.current_question()
    if not question:
        raise SessionError("沒有進行中的題目")

    now = timezone.now()
    current = compute_phase_remaining_seconds(session, now) or 0
    new_remaining = current + timer_seconds

    if new_remaining <= 0:
        _close_options_phase(session, question)
        return

    session.phase_ends_at = now + timedelta(seconds=new_remaining)
    if session.phase_started_at:
        elapsed = int((now - session.phase_started_at).total_seconds())
        session.phase_timer_seconds = elapsed + new_remaining
    else:
        session.phase_started_at = now
        session.phase_timer_seconds = new_remaining
    session.save(update_fields=["phase_started_at", "phase_timer_seconds", "phase_ends_at"])


@transaction.atomic
def next_question(session: QuizSession) -> QuizSession:
    if session.status != QuizSession.Status.RUNNING:
        raise SessionError("測驗尚未開始")

    _cancel_timer(session)

    next_index = session.current_question_index + 1
    if next_index >= len(session.question_ids):
        # Auto-open review: skip SUMMARY, go directly to REVIEW
        session.status = QuizSession.Status.REVIEW
        session.current_phase = QuizSession.Phase.CLOSED
        _clear_phase_timer(session)
        session.save(
            update_fields=[
                "status",
                "current_phase",
                "phase_started_at",
                "phase_timer_seconds",
                "phase_ends_at",
            ]
        )
        summary = session_summary_payload(session)
        broadcast_after_commit(
            session.id,
            "session:ended",
            {**session_state_payload(session), "summary": summary},
        )
        broadcast_after_commit(session.id, "session:review_opened", session_state_payload(session))
        return session

    session.current_question_index = next_index
    session.current_phase = QuizSession.Phase.STEM
    _clear_phase_timer(session)
    session.save(
        update_fields=[
            "current_question_index",
            "current_phase",
            "phase_started_at",
            "phase_timer_seconds",
            "phase_ends_at",
        ]
    )
    _emit_phase(session)
    return session


@transaction.atomic
def join_session(
    join_code: str,
    student_no: str,
    display_name: str,
) -> Participant:
    session = QuizSession.objects.get(join_code=join_code.upper())
    if session.status == QuizSession.Status.CLOSED:
        raise SessionError("場次已關閉")
    if not student_no.strip():
        raise SessionError("學號必填")

    student_no = student_no.strip()
    name = display_name.strip() or student_no
    existing = Participant.objects.filter(session=session, student_no=student_no).first()

    if session.status != QuizSession.Status.LOBBY:
        if not existing:
            raise SessionError("測驗進行中，無法新加入。請聯絡教師。")
        # Allow automatic rejoin: student can rejoin at any time
        existing.display_name = name
        existing.client_token = generate_token(24)
        existing.rejoin_allowed = False
        existing.rejoin_used = True
        existing.start_question_index = session.current_question_index
        existing.save(
            update_fields=["display_name", "client_token", "rejoin_allowed", "rejoin_used", "start_question_index"]
        )
        return existing

    if existing:
        raise SessionError("此學號已加入本場次")

    participant = Participant.objects.create(
        session=session,
        student_no=student_no,
        display_name=name,
        client_token=generate_token(24),
        rejoin_allowed=False,
        rejoin_used=False,
    )

    broadcast_after_commit(
        session.id,
        "session:participant_joined",
        {
            "student_no": participant.student_no,
            "display_name": participant.display_name,
            "participant_count": session.participants.count(),
        },
    )
    return participant


@transaction.atomic
def rescue_participant(session: QuizSession, student_no: str) -> Participant:
    if session.status != QuizSession.Status.RUNNING:
        raise SessionError("僅測驗進行中可搶救學生")
    student_no = student_no.strip()
    if not student_no:
        raise SessionError("請輸入學號")
    try:
        participant = Participant.objects.get(session=session, student_no=student_no)
    except Participant.DoesNotExist as exc:
        raise SessionError("找不到此學號的參與者（須於測驗開始前加入）") from exc
    if participant.rejoin_used:
        raise SessionError("此學生已使用過搶救重新加入，無法再次開放")
    participant.rejoin_allowed = True
    participant.save(update_fields=["rejoin_allowed"])
    return participant


@transaction.atomic
def open_review(session: QuizSession) -> QuizSession:
    if session.status not in (QuizSession.Status.SUMMARY, QuizSession.Status.REVIEW):
        raise SessionError("僅測驗結束後可開放複習")
    session.status = QuizSession.Status.REVIEW
    session.save(update_fields=["status"])
    broadcast_after_commit(session.id, "session:review_opened", session_state_payload(session))
    return session


def recover_expired_timers() -> None:
    """On startup: close expired option phases and auto-submit."""
    now = timezone.now()
    sessions = QuizSession.objects.filter(
        status=QuizSession.Status.RUNNING,
        current_phase=QuizSession.Phase.OPTIONS,
        phase_ends_at__lt=now,
    )
    for s in sessions:
        handle_phase_timeout(s.id, s.current_question_index)

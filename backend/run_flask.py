"""
Flask HTTP API（無 WebSocket）。
沿用 Django ORM 與 quiz.services，以背景輪詢處理計時逾時。
"""
from __future__ import annotations

import os
import sys
import threading
import time
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parent
os.chdir(BACKEND_DIR)
sys.path.insert(0, str(BACKEND_DIR))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings_flask")

import django

django.setup()

from django.conf import settings  # noqa: E402
from django.db import close_old_connections, transaction  # noqa: E402
from django.db.utils import IntegrityError  # noqa: E402
from django.shortcuts import get_object_or_404  # noqa: E402
from flask import Flask, g, jsonify, request, send_from_directory  # noqa: E402
from pydantic import ValidationError as PydanticValidationError  # noqa: E402
from rest_framework.exceptions import APIException, AuthenticationFailed, PermissionDenied  # noqa: E402

from quiz.api.serializers import QuestionBankDetailSerializer, QuestionBankListSerializer  # noqa: E402
from quiz.api.session_serializers import (  # noqa: E402
    AnswerResultSerializer,
    ParticipantSerializer,
    PhaseSerializer,
    SessionCreateSerializer,
    SessionJoinSerializer,
    SubmitAnswerSerializer,
    TimerAdjustSerializer,
)
from quiz.api.session_views import (  # noqa: E402
    _participant_answered,
    _participant_state_payload,
    _submitted_count,
)
from quiz.models import Answer, Question, QuestionBank, QuizSession, UserProfile, Option, Participant  # noqa: E402
from quiz.services.answers import submit_answer  # noqa: E402
from quiz.services.import_json import import_from_json_text, import_question_bank, load_import_payload  # noqa: E402
from quiz.services.login import login_student, login_teacher  # noqa: E402
from quiz.services.review import participant_review_payload  # noqa: E402
from quiz.services.session_fsm import (  # noqa: E402
    SessionError,
    adjust_timer,
    compute_phase_remaining_seconds,
    create_session,
    join_session,
    join_url_for_session,
    next_question,
    open_review,
    public_base_url,
    try_close_options_if_all_answered,
    recover_expired_timers,
    session_state_payload,
    set_phase,
    start_session,
    stem_payload,
)
from quiz.services.stats import question_stats_payload, session_summary_payload  # noqa: E402
from quiz.services.network import (  # noqa: E402
    detect_local_ipv4_addresses,
    is_loopback_host,
    is_loopback_url,
    reset_request_http_host,
    set_request_http_host,
)
from quiz.services.shuffle import get_or_create_shuffle, shuffled_options_payload  # noqa: E402

app = Flask(__name__)
FRONTEND_DIST = BACKEND_DIR.parent / "frontend" / "dist"


def _start_phase_poll_loop() -> None:
    def loop() -> None:
        while True:
            time.sleep(1)
            close_old_connections()
            try:
                recover_expired_timers()
            except Exception:
                pass

    threading.Thread(target=loop, daemon=True, name="quiz-phase-poll").start()


_start_phase_poll_loop()


def _bearer_token() -> str | None:
    auth = request.headers.get("Authorization", "")
    if auth.startswith("Bearer "):
        return auth[7:].strip()
    return request.headers.get("X-Client-Token") or request.headers.get("X-Host-Token")


def _get_session_for_host(session_id: int) -> QuizSession:
    token = _bearer_token()
    if not token:
        raise AuthenticationFailed("需要主持權杖")
    try:
        return QuizSession.objects.get(pk=session_id, host_token=token)
    except QuizSession.DoesNotExist as exc:
        raise PermissionDenied("無效的主持權杖") from exc


def _get_participant():
    from quiz.models import Participant

    token = _bearer_token()
    if not token:
        raise AuthenticationFailed("需要 client_token")

    request_tab = request.headers.get("X-Tab-Id", "").strip() or None
    request_pid_raw = request.headers.get("X-Participant-Id", "").strip()
    request_pid = int(request_pid_raw) if request_pid_raw.isdigit() else None

    # 1. Try lookup by token
    participant = None
    try:
        participant = Participant.objects.select_related("session").get(client_token=token)
    except Participant.DoesNotExist:
        participant = None

    # 2. Fallback to participant_id when token is stale (rejoin overwrote it)
    if participant is None and request_pid is not None:
        try:
            participant = Participant.objects.select_related("session").get(pk=request_pid)
        except Participant.DoesNotExist:
            participant = None

    if participant is None:
        raise AuthenticationFailed("無效的 client_token")

    # 3. Validate tab_id
    if request_tab and participant.active_tab_id and request_tab != participant.active_tab_id:
        raise _TabTakenOverError()

    return participant


class _TabTakenOverError(APIException):
    status_code = 409
    default_detail = "另一個分頁已接管此測驗，請重新加入。"
    default_code = "tab_taken_over"


def _touch_last_seen(participant):
    """每次成功的 participant API 都更新 last_seen_at。"""
    from django.utils import timezone

    from quiz.models import Participant as ParticipantModel

    ParticipantModel.objects.filter(pk=participant.pk).update(last_seen_at=timezone.now())


def _json_error(exc, status: int = 400):
    return jsonify({"detail": str(exc)}), status


def _drf_validate(serializer):
    if not serializer.is_valid():
        return jsonify(serializer.errors), 400
    return None


def _request_http_host() -> str | None:
    forwarded = request.headers.get("X-Forwarded-Host", "")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.host


@app.before_request
def _bind_request_http_host():
    g._http_host_ctx = set_request_http_host(_request_http_host())


@app.teardown_request
def _release_request_http_host(exc):
    token = getattr(g, "_http_host_ctx", None)
    if token is not None:
        reset_request_http_host(token)


@app.after_request
def _cors(resp):
    resp.headers["Access-Control-Allow-Origin"] = "*"
    resp.headers["Access-Control-Allow-Headers"] = "Authorization, Content-Type, X-Client-Token, X-Host-Token"
    resp.headers["Access-Control-Allow-Methods"] = "GET, POST, PATCH, DELETE, OPTIONS"
    return resp


@app.route("/api/<path:_path>", methods=["OPTIONS"])
def _options(_path):
    return "", 204


@app.get("/api/health/")
def health():
    return jsonify({"status": "ok", "backend": "flask"})


@app.get("/api/config/public/")
def public_config():
    configured = getattr(settings, "LAN_BASE_URL", "")
    base = public_base_url()
    if configured and configured.lower() not in {"auto", "detect"} and not is_loopback_url(configured):
        source = "env"
    elif _request_http_host() and not is_loopback_host(_request_http_host().split(":")[0]):
        source = "request"
    else:
        source = "auto"
    return jsonify(
        {
            "public_base_url": base,
            "detected_ips": detect_local_ipv4_addresses(),
            "source": source,
        }
    )


@app.get("/api/question-banks/")
def question_bank_list_get():
    banks = QuestionBank.objects.all()
    return jsonify(QuestionBankListSerializer(banks, many=True).data)


@app.post("/api/question-banks/")
def question_bank_list_post():
    try:
        if request.files.get("file"):
            uploaded = request.files["file"]
            raw_text = uploaded.read().decode("utf-8-sig")
            name = request.form.get("name") or Path(uploaded.filename).stem
            default_points = float(request.form.get("default_points") or 1)
            default_timer_seconds = int(request.form.get("default_timer_seconds") or 90)
            result = import_from_json_text(
                raw_text,
                bank_name=name,
                default_points=default_points,
                default_timer_seconds=default_timer_seconds,
            )
        else:
            body = request.get_json(silent=True) or {}
            if "questions" not in body:
                return jsonify({"detail": "請提供 JSON body（含 name、questions）或上傳 file"}), 400
            payload = load_import_payload(body)
            result = import_question_bank(payload)
    except PydanticValidationError as exc:
        return jsonify({"detail": exc.errors()}), 400
    except ValueError as exc:
        return jsonify({"detail": str(exc)}), 400

    if not result.success:
        return jsonify(
            {
                "detail": "匯入失敗，沒有任何題目寫入",
                "errors": [{"index": e.index, "message": e.message} for e in result.errors],
            }
        ), 400

    bank = QuestionBank.objects.get(pk=result.bank_id)
    data = QuestionBankDetailSerializer(bank).data
    data["import_report"] = {
        "imported_count": result.imported_count,
        "error_count": len(result.errors),
        "errors": [{"index": e.index, "message": e.message} for e in result.errors],
    }
    return jsonify(data), 201


@app.post("/api/auth/login/")
def auth_login():
    payload = request.get_json(silent=True) or {}
    role = (payload.get("role") or "").strip().lower()
    try:
        if role == "teacher":
            result = login_teacher(
                username=(payload.get("username") or "").strip(),
                password=payload.get("password") or "",
            )
        elif role == "student":
            result = login_student(
                student_no=(payload.get("student_no") or "").strip(),
                password=payload.get("password") or "",
            )
        else:
            return jsonify({"detail": "請選擇教師或學生身分"}), 400
    except ValueError as exc:
        return jsonify({"detail": str(exc)}), 401
    return jsonify(result.as_dict())


@app.get("/api/question-banks/<int:bank_id>/")
def question_bank_detail_get(bank_id: int):
    bank = get_object_or_404(QuestionBank, pk=bank_id)
    return jsonify(QuestionBankDetailSerializer(bank).data)


@app.delete("/api/question-banks/<int:bank_id>/")
def question_bank_detail_delete(bank_id: int):
    bank = get_object_or_404(QuestionBank, pk=bank_id)
    with transaction.atomic():
        bank.sessions.all().delete()
        bank.delete()
    return "", 204


@app.post("/api/sessions/")
def session_create():
    ser = SessionCreateSerializer(data=request.get_json() or {})
    err = _drf_validate(ser)
    if err:
        return err
    try:
        session = create_session(ser.validated_data["bank_id"])
    except SessionError as exc:
        return _json_error(exc)
    return jsonify(
        {
            "id": session.id,
            "join_code": session.join_code,
            "host_token": session.host_token,
            "join_url": join_url_for_session(session),
            "bank_id": session.bank_id,
            "total_questions": len(session.question_ids),
        }
    ), 201


@app.errorhandler(404)
def _api_not_found(exc):
    if not request.path.startswith("/api/"):
        raise exc
    return jsonify({"detail": "找不到資源"}), 404


@app.errorhandler(Exception)
def _api_error_handler(exc):
    if not request.path.startswith("/api/"):
        raise exc
    if isinstance(exc, IntegrityError):
        return jsonify({"detail": "資料庫欄位不一致，請在 backend 執行 python manage.py migrate 後重啟服務。"}), 500
    # Django ORM 的 .get() 找不到會拋 <Model>.DoesNotExist
    # Django 的 get_object_or_404() 拋 django.http.Http404
    from django.http import Http404

    if isinstance(exc, Http404) or exc.__class__.__name__.endswith("DoesNotExist"):
        return jsonify({"detail": "找不到資源"}), 404
    app.logger.exception("Unhandled API error on %s", request.path)
    return jsonify({"detail": "伺服器內部錯誤，請重啟後端後再試。"}), 500


@app.post("/api/sessions/join/")
def session_join():
    try:
        profile = _get_logged_in_student()
    except AuthenticationFailed as exc:
        return jsonify({"detail": "要加入測驗，請先以學生帳密登入本系統。"}), 401

    ser = SessionJoinSerializer(data=request.get_json() or {})
    err = _drf_validate(ser)
    if err:
        return err
    data = ser.validated_data

    if profile.student_no != data["student_no"]:
        return jsonify({"detail": "您目前登入的學號與您填寫的學號不符。"}), 403

    try:
        participant = join_session(
            data["join_code"],
            data["student_no"],
            data.get("display_name") or "",
            tab_id=data.get("tab_id") or "",
        )
    except QuizSession.DoesNotExist:
        return jsonify({"detail": "找不到場次"}), 404
    except SessionError as exc:
        return _json_error(exc)
    except IntegrityError:
        return jsonify({"detail": "資料庫欄位不一致，請在 backend 執行 python manage.py migrate 後重啟服務。"}), 500
    session = participant.session
    return jsonify(
        {
            "client_token": participant.client_token,
            "participant": ParticipantSerializer(participant).data,
            "session": session_state_payload(session),
        }
    ), 201


@app.get("/api/sessions/<int:session_id>/")
def session_detail(session_id: int):
    try:
        session = _get_session_for_host(session_id)
    except (AuthenticationFailed, PermissionDenied) as exc:
        return jsonify({"detail": str(exc.detail)}), 403
    participants = session.participants.all()
    return jsonify(
        {
            **session_state_payload(session),
            "stem": stem_payload(session),
            "participants": ParticipantSerializer(participants, many=True).data,
            "submitted_count": _submitted_count(session),
        }
    )


@app.get("/api/sessions/<int:session_id>/state/")
def session_state(session_id: int):
    session = get_object_or_404(QuizSession, pk=session_id)
    token = _bearer_token()
    if not token:
        return jsonify({"detail": "需要權杖"}), 401
    if token == session.host_token:
        return jsonify({**session_state_payload(session), "stem": stem_payload(session)})
    try:
        participant = _get_participant()
    except AuthenticationFailed as exc:
        return jsonify({"detail": str(exc.detail)}), 401
    if participant.session_id != session.id:
        return jsonify({"detail": "Forbidden"}), 403
    return jsonify(_participant_state_payload(participant))


@app.post("/api/sessions/<int:session_id>/start/")
def session_start(session_id: int):
    try:
        session = _get_session_for_host(session_id)
        start_session(session)
    except (AuthenticationFailed, PermissionDenied) as exc:
        return jsonify({"detail": str(exc.detail)}), 403
    except SessionError as exc:
        return _json_error(exc)
    return jsonify(session_state_payload(session))


@app.post("/api/sessions/<int:session_id>/phase/")
def session_phase(session_id: int):
    try:
        session = _get_session_for_host(session_id)
        ser = PhaseSerializer(data=request.get_json() or {})
        err = _drf_validate(ser)
        if err:
            return err
        set_phase(session, ser.validated_data["phase"], ser.validated_data.get("timer_seconds"))
        session.refresh_from_db()
    except (AuthenticationFailed, PermissionDenied) as exc:
        return jsonify({"detail": str(exc.detail)}), 403
    except SessionError as exc:
        return _json_error(exc)
    return jsonify({**session_state_payload(session), "stem": stem_payload(session)})


@app.patch("/api/sessions/<int:session_id>/timer/")
def session_timer(session_id: int):
    try:
        session = _get_session_for_host(session_id)
        ser = TimerAdjustSerializer(data=request.get_json() or {})
        err = _drf_validate(ser)
        if err:
            return err
        adjust_timer(session, ser.validated_data["timer_seconds"])
        session.refresh_from_db()
    except (AuthenticationFailed, PermissionDenied) as exc:
        return jsonify({"detail": str(exc.detail)}), 403
    except SessionError as exc:
        return _json_error(exc)
    return jsonify({**session_state_payload(session), "stem": stem_payload(session)})


@app.post("/api/sessions/<int:session_id>/next/")
def session_next(session_id: int):
    try:
        session = _get_session_for_host(session_id)
        next_question(session)
        session.refresh_from_db()
    except (AuthenticationFailed, PermissionDenied) as exc:
        return jsonify({"detail": str(exc.detail)}), 403
    except SessionError as exc:
        return _json_error(exc)
    return jsonify(session_state_payload(session))


@app.get("/api/sessions/<int:session_id>/stats/current/")
def session_stats_current(session_id: int):
    try:
        session = _get_session_for_host(session_id)
    except (AuthenticationFailed, PermissionDenied) as exc:
        return jsonify({"detail": str(exc.detail)}), 403
    question = session.current_question()
    if not question:
        return jsonify({"detail": "沒有進行中的題目"}), 404
    return jsonify(question_stats_payload(session, question))


@app.get("/api/sessions/<int:session_id>/stats/question/<int:question_id>/")
def session_stats_question(session_id: int, question_id: int):
    try:
        session = _get_session_for_host(session_id)
    except (AuthenticationFailed, PermissionDenied) as exc:
        return jsonify({"detail": str(exc.detail)}), 403
    if question_id not in session.question_ids:
        return jsonify({"detail": "Not found"}), 404
    question = get_object_or_404(Question, pk=question_id)
    return jsonify(question_stats_payload(session, question))


@app.get("/api/sessions/<int:session_id>/stats/summary/")
def session_stats_summary(session_id: int):
    try:
        session = _get_session_for_host(session_id)
    except (AuthenticationFailed, PermissionDenied) as exc:
        return jsonify({"detail": str(exc.detail)}), 403
    return jsonify(session_summary_payload(session))


@app.post("/api/sessions/<int:session_id>/open-review/")
def session_open_review(session_id: int):
    try:
        session = _get_session_for_host(session_id)
        open_review(session)
    except (AuthenticationFailed, PermissionDenied) as exc:
        return jsonify({"detail": str(exc.detail)}), 403
    except SessionError as exc:
        return _json_error(exc)
    return jsonify(session_state_payload(session))


@app.get("/api/participants/me/")
def participant_me_state():
    try:
        participant = _get_participant()
        _touch_last_seen(participant)
    except AuthenticationFailed as exc:
        return jsonify({"detail": str(exc.detail)}), 401
    except _TabTakenOverError as exc:
        return jsonify({"detail": str(exc.detail), "code": "tab_taken_over"}), 409
    return jsonify(_participant_state_payload(participant))


@app.get("/api/participants/me/review/")
def participant_me_review():
    try:
        participant = _get_participant()
        _touch_last_seen(participant)
        data = participant_review_payload(participant)
    except AuthenticationFailed as exc:
        return jsonify({"detail": str(exc.detail)}), 401
    except _TabTakenOverError as exc:
        return jsonify({"detail": str(exc.detail), "code": "tab_taken_over"}), 409
    except ValueError as exc:
        return jsonify({"detail": str(exc)}), 403
    return jsonify(data)


@app.post("/api/participants/me/options/")
def participant_me_options():
    try:
        participant = _get_participant()
        _touch_last_seen(participant)
    except AuthenticationFailed as exc:
        return jsonify({"detail": str(exc.detail)}), 401
    except _TabTakenOverError as exc:
        return jsonify({"detail": str(exc.detail), "code": "tab_taken_over"}), 409
    session = participant.session
    session.refresh_from_db()
    if session.current_phase != QuizSession.Phase.OPTIONS:
        return jsonify({"detail": "目前尚未開放選項"}), 400
    question = session.current_question()
    if not question:
        return jsonify({"detail": "沒有題目"}), 400
    if session.current_question_index < participant.start_question_index:
        return jsonify({"detail": "此題已結束，無法取回選項。請等待目前開放的題目。"}), 403
    permutation = get_or_create_shuffle(session, question, participant)
    return jsonify(
        {
            "question_id": question.id,
            "type": question.type,
            "options": shuffled_options_payload(question, permutation),
            "phase_started_at": session.phase_started_at.isoformat() if session.phase_started_at else None,
            "phase_timer_seconds": session.phase_timer_seconds,
            "phase_remaining_seconds": compute_phase_remaining_seconds(session),
        }
    )


@app.post("/api/participants/me/answers/")
def participant_me_submit():
    try:
        participant = _get_participant()
        _touch_last_seen(participant)
    except AuthenticationFailed as exc:
        return jsonify({"detail": str(exc.detail)}), 401
    except _TabTakenOverError as exc:
        return jsonify({"detail": str(exc.detail), "code": "tab_taken_over"}), 409
    session = participant.session
    session.refresh_from_db()
    if session.current_phase != QuizSession.Phase.OPTIONS:
        return jsonify({"detail": "目前無法提交"}), 400
    question = session.current_question()
    if not question:
        return jsonify({"detail": "沒有題目"}), 400
    if session.current_question_index < participant.start_question_index:
        return jsonify({"detail": "此題已結束，無法提交答案。"}), 403
    ser = SubmitAnswerSerializer(data=request.get_json() or {})
    err = _drf_validate(ser)
    if err:
        return err
    option_ids = ser.validated_data["option_ids"]
    if question.type == Question.Type.SINGLE and len(option_ids) > 1:
        return jsonify({"detail": "單選題只能選一項"}), 400
    try:
        answer = submit_answer(participant=participant, question=question, selected_option_ids=option_ids)
    except ValueError as exc:
        return jsonify({"detail": str(exc)}), 400
    try_close_options_if_all_answered(session, question)
    return jsonify({"message": "已送出", "answer": AnswerResultSerializer(answer).data}), 201


def _get_logged_in_student() -> UserProfile:
    token = _bearer_token()
    if not token:
        raise AuthenticationFailed("需要登入權杖")
    profile = UserProfile.objects.filter(login_token=token).first()
    if not profile:
        raise AuthenticationFailed("登入權杖無效或已過期")
    return profile


def student_history_detail_payload(participant: Participant) -> dict:
    session = participant.session
    questions_data = []
    total_score = 0.0
    max_total = 0.0

    for idx, qid in enumerate(session.question_ids):
        question = Question.objects.filter(pk=qid).prefetch_related("options").first()
        if not question:
            continue
        max_total += float(question.points)

        answer = Answer.objects.filter(
            session=session,
            question=question,
            participant=participant,
        ).first()

        correct_letters = sorted(
            Option.objects.filter(question=question, is_correct=True).values_list("letter", flat=True)
        )
        selected_letters: list[str] = []
        score = 0.0
        is_full = False
        submit_source = None

        if answer:
            score = float(answer.score)
            is_full = answer.is_full_score
            submit_source = answer.submit_source
            total_score += score
            selected_letters = sorted(
                Option.objects.filter(
                    pk__in=answer.selected_option_ids,
                    question=question,
                ).values_list("letter", flat=True)
            )

        options_display = [
            {"letter": o.letter, "label_text": o.label_text}
            for o in question.options.order_by("sort_order")
        ]

        questions_data.append(
            {
                "question_index": idx,
                "stem_text": question.stem_text,
                "type": question.type,
                "category": question.category,
                "points": str(question.points),
                "your_answer": "".join(selected_letters) if selected_letters else None,
                "correct_answer": "".join(correct_letters),
                "score": score,
                "is_full_score": is_full,
                "submit_source": submit_source,
                "explanation_text": question.explanation_text,
                "options": options_display,
            }
        )

    from django.db.models import Model
    return {
        "session_id": session.id,
        "student_no": participant.student_no,
        "display_name": participant.display_name,
        "bank_name": session.bank.name,
        "total_score": round(total_score, 2),
        "max_total_score": round(max_total, 2),
        "questions": questions_data,
    }


@app.get("/api/students/history/")
def student_history_list():
    try:
        profile = _get_logged_in_student()
    except AuthenticationFailed as exc:
        return jsonify({"detail": str(exc.detail)}), 401

    participants = Participant.objects.filter(
        student_no=profile.student_no
    ).select_related("session", "session__bank").order_by("-id")

    try:
        page = int(request.args.get("page", 1))
        if page < 1:
            page = 1
    except ValueError:
        page = 1

    per_page = 5
    total_count = participants.count()
    import math
    total_pages = math.ceil(total_count / per_page) if total_count > 0 else 1

    start_index = (page - 1) * per_page
    end_index = start_index + per_page
    page_items = participants[start_index:end_index]

    items_data = []
    for p in page_items:
        session = p.session
        max_score = 0.0
        for qid in session.question_snapshot:
            q = Question.objects.filter(pk=qid).first()
            if q:
                max_score += float(q.points)

        answers = Answer.objects.filter(session=session, participant=p)
        actual_score = sum(float(a.score) for a in answers)

        items_data.append({
            "participant_id": p.id,
            "session_id": session.id,
            "join_code": session.join_code,
            "bank_name": session.bank.name,
            "session_status": session.status,
            "joined_at": p.joined_at.isoformat() if p.joined_at else None,
            "actual_score": round(actual_score, 2),
            "max_score": round(max_score, 2),
        })

    return jsonify({
        "items": items_data,
        "page": page,
        "total_pages": total_pages,
        "total_count": total_count,
    })


@app.get("/api/students/history/<int:participant_id>/")
def student_history_detail(participant_id: int):
    try:
        profile = _get_logged_in_student()
    except AuthenticationFailed as exc:
        return jsonify({"detail": str(exc.detail)}), 401

    participant = get_object_or_404(Participant, pk=participant_id)
    if participant.student_no != profile.student_no:
        return jsonify({"detail": "Forbidden"}), 403

    payload = student_history_detail_payload(participant)
    return jsonify(payload)


def _serve_spa(path: str):
    if not FRONTEND_DIST.exists():
        return jsonify({"detail": "前端尚未建置，請執行 npm run build"}), 503
    if path:
        candidate = FRONTEND_DIST / path
        if candidate.is_file():
            return send_from_directory(FRONTEND_DIST, path)
    return send_from_directory(FRONTEND_DIST, "index.html")


@app.get("/")
def spa_root():
    return _serve_spa("")


@app.get("/<path:path>")
def spa_catchall(path: str):
    if path.startswith("api/"):
        return jsonify({"detail": "Not found"}), 404
    return _serve_spa(path)


if __name__ == "__main__":
    port = int(os.environ.get("PORT", "5000"))
    app.run(host="0.0.0.0", port=port, threaded=True)

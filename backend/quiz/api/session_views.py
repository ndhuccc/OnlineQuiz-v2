from django.conf import settings
from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework import status
from rest_framework.decorators import api_view
from rest_framework.response import Response

from quiz.models import Answer, Participant, Question, QuizSession
from quiz.services.answers import submit_answer
from quiz.services.broadcast import broadcast
from quiz.services.review import participant_review_payload
from quiz.services.session_fsm import (
    SessionError,
    adjust_timer,
    compute_phase_remaining_seconds,
    create_session,
    join_session,
    join_url_for_session,
    next_question,
    open_review,
    public_base_url,
    question_meta_payload,
    session_state_payload,
    set_phase,
    start_session,
    stem_payload,
    try_close_options_if_all_answered,
)
from quiz.services.session_fsm import push_question_stats
from quiz.services.stats import question_stats_payload, session_summary_payload
from quiz.services.shuffle import get_or_create_shuffle, shuffled_options_payload

from .auth_helpers import bearer_token, get_participant, get_session_for_host
from .session_serializers import (
    AnswerResultSerializer,
    ParticipantSerializer,
    PhaseSerializer,
    SessionCreateSerializer,
    SessionJoinSerializer,
    SubmitAnswerSerializer,
    TimerAdjustSerializer,
)


def _touch_last_seen(participant: Participant) -> None:
    """每次成功的 participant API 都更新 last_seen_at，便於日後偵測幽靈分頁。"""
    Participant.objects.filter(pk=participant.pk).update(last_seen_at=timezone.now())


@api_view(["POST"])
def session_create(request):
    ser = SessionCreateSerializer(data=request.data)
    ser.is_valid(raise_exception=True)
    try:
        session = create_session(ser.validated_data["bank_id"])
    except SessionError as exc:
        return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)

    return Response(
        {
            "id": session.id,
            "join_code": session.join_code,
            "host_token": session.host_token,
            "join_url": join_url_for_session(session),
            "bank_id": session.bank_id,
            "total_questions": len(session.question_ids),
        },
        status=status.HTTP_201_CREATED,
    )


@api_view(["POST"])
def session_join(request):
    ser = SessionJoinSerializer(data=request.data)
    ser.is_valid(raise_exception=True)
    data = ser.validated_data
    try:
        participant = join_session(
            data["join_code"],
            data["student_no"],
            data.get("display_name") or "",
            tab_id=data.get("tab_id") or "",
        )
    except QuizSession.DoesNotExist:
        return Response({"detail": "找不到場次"}, status=status.HTTP_404_NOT_FOUND)
    except SessionError as exc:
        return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)

    session = participant.session
    return Response(
        {
            "client_token": participant.client_token,
            "participant": ParticipantSerializer(participant).data,
            "session": session_state_payload(session),
        },
        status=status.HTTP_201_CREATED,
    )


@api_view(["GET"])
def session_detail(request, session_id: int):
    session = get_session_for_host(request, session_id)
    participants = session.participants.all()
    return Response(
        {
            **session_state_payload(session),
            "stem": stem_payload(session),
            "participants": ParticipantSerializer(participants, many=True).data,
            "submitted_count": _submitted_count(session),
        }
    )


@api_view(["GET"])
def session_state(request, session_id: int):
    """重連用：主持或學生皆可（需對應 token）。"""
    session = get_object_or_404(QuizSession, pk=session_id)
    token = bearer_token(request)
    if not token:
        return Response({"detail": "需要權杖"}, status=status.HTTP_401_UNAUTHORIZED)

    if token == session.host_token:
        return Response(
            {
                **session_state_payload(session),
                "stem": stem_payload(session),
            }
        )

    try:
        participant = get_participant(request)
    except Exception as exc:
        from rest_framework.exceptions import APIException

        if isinstance(exc, APIException):
            raise
        return Response({"detail": "無效的權杖"}, status=status.HTTP_401_UNAUTHORIZED)

    if participant.session_id != session.id:
        return Response(status=status.HTTP_403_FORBIDDEN)

    return Response(_participant_state_payload(participant))


@api_view(["POST"])
def session_start(request, session_id: int):
    session = get_session_for_host(request, session_id)
    try:
        start_session(session)
    except SessionError as exc:
        return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)
    return Response(session_state_payload(session))


@api_view(["POST"])
def session_phase(request, session_id: int):
    session = get_session_for_host(request, session_id)
    ser = PhaseSerializer(data=request.data)
    ser.is_valid(raise_exception=True)
    try:
        set_phase(
            session,
            ser.validated_data["phase"],
            ser.validated_data.get("timer_seconds"),
        )
    except SessionError as exc:
        return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)
    session.refresh_from_db()
    return Response(
        {
            **session_state_payload(session),
            "stem": stem_payload(session),
        }
    )


@api_view(["PATCH"])
def session_timer(request, session_id: int):
    session = get_session_for_host(request, session_id)
    ser = TimerAdjustSerializer(data=request.data)
    ser.is_valid(raise_exception=True)
    try:
        adjust_timer(session, ser.validated_data["timer_seconds"])
    except SessionError as exc:
        return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)
    session.refresh_from_db()
    return Response(
        {
            **session_state_payload(session),
            "stem": stem_payload(session),
        }
    )


@api_view(["POST"])
def session_next(request, session_id: int):
    session = get_session_for_host(request, session_id)
    try:
        next_question(session)
    except SessionError as exc:
        return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)
    session.refresh_from_db()
    return Response(session_state_payload(session))


@api_view(["GET"])
def session_stats_current(request, session_id: int):
    session = get_session_for_host(request, session_id)
    question = session.current_question()
    if not question:
        return Response({"detail": "沒有進行中的題目"}, status=status.HTTP_404_NOT_FOUND)
    return Response(question_stats_payload(session, question))


@api_view(["GET"])
def session_stats_question(request, session_id: int, question_id: int):
    session = get_session_for_host(request, session_id)
    if question_id not in session.question_ids:
        return Response(status=status.HTTP_404_NOT_FOUND)
    question = get_object_or_404(Question, pk=question_id)
    return Response(question_stats_payload(session, question))


@api_view(["GET"])
def session_stats_summary(request, session_id: int):
    session = get_session_for_host(request, session_id)
    return Response(session_summary_payload(session))


@api_view(["POST"])
def session_open_review(request, session_id: int):
    session = get_session_for_host(request, session_id)
    try:
        open_review(session)
    except SessionError as exc:
        return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)
    return Response(session_state_payload(session))


@api_view(["GET"])
def participant_me_review(request):
    participant = get_participant(request)
    _touch_last_seen(participant)
    try:
        data = participant_review_payload(participant)
    except ValueError as exc:
        return Response({"detail": str(exc)}, status=status.HTTP_403_FORBIDDEN)
    return Response(data)


@api_view(["GET"])
def participant_me_state(request):
    participant = get_participant(request)
    _touch_last_seen(participant)
    return Response(_participant_state_payload(participant))


@api_view(["POST"])
def participant_me_options(request):
    participant = get_participant(request)
    _touch_last_seen(participant)
    session = participant.session
    session.refresh_from_db()
    if session.current_phase != QuizSession.Phase.OPTIONS:
        return Response({"detail": "目前尚未開放選項"}, status=status.HTTP_400_BAD_REQUEST)

    question = session.current_question()
    if not question:
        return Response({"detail": "沒有題目"}, status=status.HTTP_400_BAD_REQUEST)

    if session.current_question_index < participant.start_question_index:
        return Response(
            {"detail": "此題已結束，無法取回選項。請等待目前開放的題目。"},
            status=status.HTTP_403_FORBIDDEN,
        )

    permutation = get_or_create_shuffle(session, question, participant)
    return Response(
        {
            "question_id": question.id,
            "type": question.type,
            "options": shuffled_options_payload(question, permutation),
            "phase_started_at": session.phase_started_at.isoformat() if session.phase_started_at else None,
            "phase_timer_seconds": session.phase_timer_seconds,
            "phase_remaining_seconds": compute_phase_remaining_seconds(session),
        }
    )


@api_view(["POST"])
def participant_me_submit(request):
    participant = get_participant(request)
    _touch_last_seen(participant)
    session = participant.session
    session.refresh_from_db()
    if session.current_phase != QuizSession.Phase.OPTIONS:
        return Response({"detail": "目前無法提交"}, status=status.HTTP_400_BAD_REQUEST)

    question = session.current_question()
    if not question:
        return Response({"detail": "沒有題目"}, status=status.HTTP_400_BAD_REQUEST)

    if session.current_question_index < participant.start_question_index:
        return Response(
            {"detail": "此題已結束，無法提交答案。"},
            status=status.HTTP_403_FORBIDDEN,
        )

    ser = SubmitAnswerSerializer(data=request.data)
    ser.is_valid(raise_exception=True)
    option_ids = ser.validated_data["option_ids"]

    if question.type == Question.Type.SINGLE and len(option_ids) > 1:
        return Response({"detail": "單選題只能選一項"}, status=status.HTTP_400_BAD_REQUEST)

    try:
        answer = submit_answer(
            participant=participant,
            question=question,
            selected_option_ids=option_ids,
        )
    except ValueError as exc:
        return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)

    try_close_options_if_all_answered(session, question)

    broadcast(
        session.id,
        "session:answer_submitted",
        {
            "submitted_count": Answer.objects.filter(session=session, question=question).count(),
            "total_participants": session.participants.count(),
        },
    )
    push_question_stats(session)

    return Response(
        {
            "message": "已送出",
            "answer": AnswerResultSerializer(answer).data,
        },
        status=status.HTTP_201_CREATED,
    )


def _participant_state_payload(participant) -> dict:
    session = participant.session
    session.refresh_from_db()
    payload = {
        **session_state_payload(session),
        "has_answered": _participant_answered(participant, session),
        "start_question_index": participant.start_question_index,
    }
    meta = question_meta_payload(session)
    if meta:
        payload["question"] = meta
    return payload


def _submitted_count(session: QuizSession) -> int:
    question = session.current_question()
    if not question:
        return 0
    return Answer.objects.filter(session=session, question=question).count()


def _participant_answered(participant, session: QuizSession) -> bool:
    question = session.current_question()
    if not question:
        return False
    return Answer.objects.filter(
        session=session,
        question=question,
        participant=participant,
    ).exists()

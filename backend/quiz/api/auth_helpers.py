from rest_framework import status
from rest_framework.exceptions import AuthenticationFailed, NotFound, PermissionDenied
from rest_framework.response import Response
from rest_framework.views import exception_handler

from quiz.models import Participant, QuizSession


class TabTakenOver(AuthenticationFailed):
    """Raised when a request's X-Tab-Id does not match the participant's active_tab_id.

    Translates to HTTP 409 Conflict so the frontend can show
    「另一個分頁已接管」訊息給學生。
    """

    status_code = status.HTTP_409_CONFLICT
    default_detail = "另一個分頁已接管此測驗，請重新加入。"
    default_code = "tab_taken_over"


def bearer_token(request) -> str | None:
    auth = request.headers.get("Authorization", "")
    if auth.startswith("Bearer "):
        return auth[7:].strip()
    return request.headers.get("X-Client-Token") or request.headers.get("X-Host-Token")


def tab_id_from_request(request) -> str | None:
    """前端為每個分頁產生的 UUID，存在 sessionStorage，每次 request 帶在 X-Tab-Id header。"""
    tid = request.headers.get("X-Tab-Id", "").strip()
    return tid or None


def get_session_for_host(request, session_id: int) -> QuizSession:
    token = bearer_token(request)
    if not token:
        raise AuthenticationFailed("需要主持權杖")
    try:
        return QuizSession.objects.get(pk=session_id, host_token=token)
    except QuizSession.DoesNotExist:
        raise PermissionDenied("無效的主持權杖") from None


def get_participant(request) -> Participant:
    """Look up the participant by client_token, and validate the request's tab_id.

    Falls back to lookup by (X-Participant-Id) header when the token is stale
    (rejoin from another tab regenerated the token). If found by participant_id
    but the token doesn't match → raise TabTakenOver (409) instead of 401.

    Raises TabTakenOver (409) if a different tab is currently active for this participant.
    """
    token = bearer_token(request)
    if not token:
        raise AuthenticationFailed("需要 client_token")

    request_tab = tab_id_from_request(request)
    request_pid = request.headers.get("X-Participant-Id", "").strip() or None

    # 1. Try lookup by token first
    participant = None
    try:
        participant = Participant.objects.select_related("session").get(client_token=token)
    except Participant.DoesNotExist:
        participant = None

    # 2. If not found and we have participant_id, look up by that
    if participant is None and request_pid:
        try:
            participant = Participant.objects.select_related("session").get(pk=int(request_pid))
        except (Participant.DoesNotExist, ValueError):
            participant = None

    if participant is None:
        raise AuthenticationFailed("無效的 client_token")

    # 3. Validate tab_id (only if request sent one and participant has one stored)
    if request_tab and participant.active_tab_id and request_tab != participant.active_tab_id:
        raise TabTakenOver()

    return participant


def custom_exception_handler(exc, context):
    """DRF exception handler that maps TabTakenOver to 409 JSON."""
    if isinstance(exc, TabTakenOver):
        return Response(
            {"detail": str(exc.detail), "code": exc.default_code},
            status=status.HTTP_409_CONFLICT,
        )
    return exception_handler(exc, context)

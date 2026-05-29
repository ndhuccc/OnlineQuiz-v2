from rest_framework.exceptions import AuthenticationFailed, NotFound, PermissionDenied

from quiz.models import Participant, QuizSession


def bearer_token(request) -> str | None:
    auth = request.headers.get("Authorization", "")
    if auth.startswith("Bearer "):
        return auth[7:].strip()
    return request.headers.get("X-Client-Token") or request.headers.get("X-Host-Token")


def get_session_for_host(request, session_id: int) -> QuizSession:
    token = bearer_token(request)
    if not token:
        raise AuthenticationFailed("需要主持權杖")
    try:
        return QuizSession.objects.get(pk=session_id, host_token=token)
    except QuizSession.DoesNotExist:
        raise PermissionDenied("無效的主持權杖") from None


def get_participant(request) -> Participant:
    token = bearer_token(request)
    if not token:
        raise AuthenticationFailed("需要 client_token")
    try:
        return Participant.objects.select_related("session").get(client_token=token)
    except Participant.DoesNotExist:
        raise AuthenticationFailed("無效的 client_token") from None

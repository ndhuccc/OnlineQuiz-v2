"""WebSocket 已停用；前後端改以 HTTP 輪詢同步。"""


def session_group(session_id: int) -> str:
    return f"session_{session_id}"


def broadcast(session_id: int, event_type: str, payload: dict) -> None:
    return


def broadcast_after_commit(session_id: int, event_type: str, payload: dict) -> None:
    return

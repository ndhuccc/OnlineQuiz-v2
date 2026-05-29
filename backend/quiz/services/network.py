"""偵測本機 IP，供加入連結／QR Code 使用。"""
from __future__ import annotations

import socket
from contextvars import ContextVar
from urllib.parse import urlparse

_request_http_host: ContextVar[str | None] = ContextVar("request_http_host", default=None)


def set_request_http_host(host: str | None):
    return _request_http_host.set(host)


def reset_request_http_host(token) -> None:
    _request_http_host.reset(token)


def get_request_http_host() -> str | None:
    return _request_http_host.get()


def is_loopback_host(host: str) -> bool:
    host = (host or "").strip().lower()
    return host in {"localhost", "127.0.0.1", "::1", "[::1]", "0.0.0.0"}


def is_loopback_url(url: str) -> bool:
    if not url:
        return True
    parsed = urlparse(url if "://" in url else f"http://{url}")
    return is_loopback_host(parsed.hostname or "")


def detect_local_ipv4_addresses() -> list[str]:
    """列出本機非 loopback 的 IPv4（含 UDP 外連與 hostname 解析）。"""
    found: list[str] = []

    def add(ip: str | None) -> None:
        if not ip or ip.startswith("127.") or ip in found:
            return
        found.append(ip)

    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
            sock.connect(("8.8.8.8", 80))
            add(sock.getsockname()[0])
    except OSError:
        pass

    try:
        for info in socket.getaddrinfo(socket.gethostname(), None, socket.AF_INET):
            add(info[4][0])
    except OSError:
        pass

    return found


def pick_preferred_ipv4() -> str | None:
    ips = detect_local_ipv4_addresses()
    if not ips:
        return None

    def rank(ip: str) -> tuple[int, str]:
        if ip.startswith("192.168."):
            return (0, ip)
        if ip.startswith("10."):
            return (1, ip)
        parts = ip.split(".")
        if len(parts) == 4 and parts[0] == "172":
            try:
                second = int(parts[1])
            except ValueError:
                second = -1
            if 16 <= second <= 31:
                return (2, ip)
        return (3, ip)

    return sorted(ips, key=rank)[0]


def resolve_base_url(*, configured: str, port: int, http_host: str | None = None) -> str:
    """
    決定學生加入用的 base URL。
    優先序：.env 設定 > 請求 Host（非 localhost）> 自動偵測 IP。
    """
    configured = (configured or "").strip()
    if configured and configured.lower() not in {"auto", "detect"} and not is_loopback_url(configured):
        return configured.rstrip("/")

    host = (http_host or get_request_http_host() or "").strip()
    if host and not is_loopback_host(host.split(":")[0]):
        if "://" in host:
            return host.rstrip("/")
        return f"http://{host}".rstrip("/")

    ip = pick_preferred_ipv4()
    if ip:
        return f"http://{ip}:{port}"

    if configured:
        return configured.rstrip("/")
    return f"http://127.0.0.1:{port}"

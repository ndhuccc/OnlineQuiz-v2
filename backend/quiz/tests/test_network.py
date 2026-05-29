from quiz.services.network import detect_local_ipv4_addresses, is_loopback_host, is_loopback_url, pick_preferred_ipv4, resolve_base_url


def test_is_loopback_host():
    assert is_loopback_host("localhost")
    assert is_loopback_host("127.0.0.1")
    assert not is_loopback_host("192.168.1.10")


def test_is_loopback_url():
    assert is_loopback_url("http://127.0.0.1:3080")
    assert not is_loopback_url("http://192.168.1.10:3080")


def test_resolve_base_url_prefers_configured():
    url = resolve_base_url(configured="http://example.com:3080", port=3080)
    assert url == "http://example.com:3080"


def test_resolve_base_url_uses_request_host():
    url = resolve_base_url(configured="", port=3080, http_host="192.168.2.159:3080")
    assert url == "http://192.168.2.159:3080"


def test_resolve_base_url_auto_detect(monkeypatch):
    monkeypatch.setattr("quiz.services.network.pick_preferred_ipv4", lambda: "192.168.2.100")
    url = resolve_base_url(configured="", port=3080)
    assert url == "http://192.168.2.100:3080"


def test_detect_local_ipv4_addresses_returns_list():
    ips = detect_local_ipv4_addresses()
    assert isinstance(ips, list)
    assert all("." in ip and not ip.startswith("127.") for ip in ips)


def test_pick_preferred_ipv4_prefers_private_lan(monkeypatch):
    monkeypatch.setattr(
        "quiz.services.network.detect_local_ipv4_addresses",
        lambda: ["134.208.64.77", "192.168.2.159", "10.0.0.5"],
    )
    assert pick_preferred_ipv4() == "192.168.2.159"

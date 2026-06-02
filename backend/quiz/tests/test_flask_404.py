"""Tests for the Flask app's error handling — 404 for missing resources.

Pre-fix: the global @errorhandler(Exception) swallowed Http404 / DoesNotExist
and returned 500 'Internal Server Error' for any missing object.
Post-fix: those should return 404 with a clean '找不到資源' message.
"""
import pytest


@pytest.mark.django_db
def test_session_state_returns_404_for_missing_session():
    """GET /api/sessions/{nonexistent}/state/ should be 404, not 500."""
    from run_flask import app

    client = app.test_client()
    res = client.get("/api/sessions/99999/state/")
    assert res.status_code == 404, res.get_data(as_text=True)
    body = res.get_json()
    assert "找不到" in body["detail"]


@pytest.mark.django_db
def test_session_detail_returns_404_for_missing_session():
    """Same protection for /api/sessions/{id}/."""
    from run_flask import app

    client = app.test_client()
    res = client.get("/api/sessions/99999/", headers={"Authorization": "Bearer fake"})
    assert res.status_code in (403, 404), res.get_data(as_text=True)
    # The detail page requires a valid host_token, so 403 is also acceptable here
    # (host_token mismatch on a non-existent session). Either way: not 500.


@pytest.mark.django_db
def test_health_endpoint_still_works():
    """Sanity: the fix didn't break the happy path."""
    from run_flask import app

    client = app.test_client()
    res = client.get("/api/health/")
    assert res.status_code == 200
    body = res.get_json()
    assert body.get("status") == "ok"

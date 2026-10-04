import json

from api_agent.config import get_settings
from api_agent.tools.api_tools import (
    create_user,
    get_user_stats,
    get_users_by_name,
    list_users,
    update_user_status_by_name,
)


def _parse(raw: str) -> dict:
    return json.loads(raw)


def test_create_user_success(api_server, api_url):
    parsed = _parse(create_user.invoke({"name": "Alex"}))
    assert parsed["status"] == "success"
    assert parsed["http_status"] == 201
    assert parsed["data"]["name"] == "Alex"
    assert parsed["data"]["duplicate"] is False
    assert parsed["errors"] is None


def test_get_users_by_name_not_found(api_server, api_url):
    parsed = _parse(get_users_by_name.invoke({"name": "Nobody"}))
    assert parsed["status"] == "error"
    assert parsed["http_status"] == 404
    assert parsed["data"] is None
    assert parsed["errors"] is not None


def test_update_status_and_stats(api_server, api_url):
    create_user.invoke({"name": "Alex"})
    parsed = _parse(update_user_status_by_name.invoke({"name": "Alex", "status": "blocked"}))
    assert parsed["status"] == "success"
    assert parsed["data"]["status"] == "blocked"
    stats = _parse(get_user_stats.invoke({}))
    assert stats["data"] == {"total": 1, "active": 0, "blocked": 1}


def test_cyrillic_name_roundtrip(api_server, api_url):
    parsed = _parse(create_user.invoke({"name": "Иван", "email": "ivan@mail.ru"}))
    assert parsed["status"] == "success"
    found = _parse(get_users_by_name.invoke({"name": "Иван"}))
    assert found["data"][0]["name"] == "Иван"


def test_connection_error_returns_structured_error(api_server, monkeypatch):
    monkeypatch.setenv("AGENT_API_BASE_URL", "http://127.0.0.1:9")
    get_settings.cache_clear()
    parsed = _parse(list_users.invoke({}))
    assert parsed["status"] == "error"
    assert parsed["http_status"] is None
    assert "connection" in parsed["errors"].lower()
    get_settings.cache_clear()

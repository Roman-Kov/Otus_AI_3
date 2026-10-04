import json

from api_agent.config import get_settings
from api_agent.tools.api_tools import (
    add_book,
    delete_book,
    get_book_by_title,
    get_catalog_stats,
    list_books,
    rename_book,
)


def _parse(raw: str) -> dict:
    return json.loads(raw)


def test_add_book_success(api_server, api_url):
    parsed = _parse(add_book.invoke({"title": "Мастер и Маргарита"}))
    assert parsed["status"] == "success"
    assert parsed["http_status"] == 201
    assert parsed["data"]["title"] == "Мастер и Маргарита"
    assert parsed["errors"] is None


def test_add_book_duplicate_409(api_server, api_url):
    add_book.invoke({"title": "Война и мир"})
    parsed = _parse(add_book.invoke({"title": "Война и мир"}))
    assert parsed["status"] == "error"
    assert parsed["http_status"] == 409
    assert parsed["data"] is None
    assert parsed["errors"] is not None


def test_get_book_not_found(api_server, api_url):
    parsed = _parse(get_book_by_title.invoke({"title": "Призрак"}))
    assert parsed["status"] == "error"
    assert parsed["http_status"] == 404
    assert parsed["data"] is None
    assert parsed["errors"] is not None


def test_rename_book_success(api_server, api_url):
    add_book.invoke({"title": "Мы"})
    parsed = _parse(rename_book.invoke({"title": "Мы", "new_title": "Мы (замятин)"}))
    assert parsed["status"] == "success"
    assert parsed["data"]["title"] == "Мы (замятин)"


def test_delete_book_204_and_stats(api_server, api_url):
    add_book.invoke({"title": "Тихий Дон"})
    parsed = _parse(delete_book.invoke({"title": "Тихий Дон"}))
    assert parsed["status"] == "success"
    assert parsed["http_status"] == 204
    assert parsed["data"] is None
    stats = _parse(get_catalog_stats.invoke({}))
    assert stats["data"] == {"total": 0}


def test_cyrillic_and_special_chars_roundtrip(api_server, api_url):
    title = "Что делать? (чернышевский)"
    parsed = _parse(add_book.invoke({"title": title}))
    assert parsed["status"] == "success"
    found = _parse(get_book_by_title.invoke({"title": title}))
    assert found["data"]["title"] == title


def test_connection_error_returns_structured_error(api_server, monkeypatch):
    monkeypatch.setenv("AGENT_API_BASE_URL", "http://127.0.0.1:9")
    get_settings.cache_clear()
    parsed = _parse(list_books.invoke({}))
    assert parsed["status"] == "error"
    assert parsed["http_status"] is None
    assert "connection" in parsed["errors"].lower()
    get_settings.cache_clear()

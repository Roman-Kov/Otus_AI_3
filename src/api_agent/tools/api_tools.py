import json
import logging
from urllib.parse import quote

import httpx
from langchain_core.tools import tool

from ..config import get_settings

logger = logging.getLogger("api_agent.tools")


def _client() -> httpx.Client:
    return httpx.Client(base_url=get_settings().api_base_url, timeout=10.0)


def _result(response: httpx.Response) -> str:
    try:
        data = response.json()
    except ValueError:
        data = response.text or None
    errors = f"HTTP {response.status_code}: {data}" if response.is_error else None
    result = {
        "status": "error" if response.is_error else "success",
        "http_status": response.status_code,
        "data": None if response.is_error else data,
        "errors": errors,
    }
    logger.info("tool result: %s", json.dumps(result, ensure_ascii=False))
    return json.dumps(result, ensure_ascii=False)


def _request(method: str, path: str, **kwargs: object) -> str:
    try:
        with _client() as client:
            response = client.request(method, path, **kwargs)
        return _result(response)
    except httpx.HTTPError as exc:
        result = {
            "status": "error",
            "http_status": None,
            "data": None,
            "errors": f"connection error: {exc}",
        }
        logger.info("tool result: %s", json.dumps(result, ensure_ascii=False))
        return json.dumps(result, ensure_ascii=False)


@tool
def add_book(title: str) -> str:
    """Добавить книгу в каталог по названию.

    Возвращает данные созданной книги. Если название уже есть в каталоге — ошибку 409.
    """
    return _request("POST", "/books", json={"title": title})


@tool
def get_book_by_title(title: str) -> str:
    """Найти книгу по названию. Возвращает данные книги."""
    return _request("GET", f"/books/{quote(title, safe='')}")


@tool
def rename_book(title: str, new_title: str) -> str:
    """Переименовать книгу.

    Текущее название должно существовать, новое — быть свободным (иначе 409).
    """
    return _request("PATCH", f"/books/{quote(title, safe='')}", json={"new_title": new_title})


@tool
def delete_book(title: str) -> str:
    """Удалить книгу из каталога по названию."""
    return _request("DELETE", f"/books/{quote(title, safe='')}")


@tool
def list_books() -> str:
    """Получить список всех книг каталога."""
    return _request("GET", "/books")


@tool
def get_catalog_stats() -> str:
    """Получить статистику каталога: сколько всего книг."""
    return _request("GET", "/stats")


API_TOOLS = [add_book, get_book_by_title, rename_book, delete_book, list_books, get_catalog_stats]

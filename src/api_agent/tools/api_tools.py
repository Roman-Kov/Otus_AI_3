import json
import logging

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
        data = response.text
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
def create_user(name: str, email: str | None = None) -> str:
    """Создать пользователя с заданным именем (email необязателен).

    Возвращает данные созданного пользователя и флаг duplicate=true, если имя уже существовало.
    """
    return _request("POST", "/users", json={"name": name, "email": email})


@tool
def get_users_by_name(name: str) -> str:
    """Найти пользователей по имени. Возвращает список всех совпадений."""
    return _request("GET", f"/users/{name}")


@tool
def update_user_status_by_name(name: str, status: str) -> str:
    """Изменить статус пользователя ('active' или 'blocked') по имени.

    Работает только если пользователь с таким именем ровно один.
    """
    return _request("PATCH", f"/users/{name}/status", json={"status": status})


@tool
def list_users() -> str:
    """Получить список всех пользователей."""
    return _request("GET", "/users")


@tool
def get_user_stats() -> str:
    """Получить статистику: сколько всего, активных и заблокированных пользователей."""
    return _request("GET", "/stats")


API_TOOLS = [create_user, get_users_by_name, update_user_status_by_name, list_users, get_user_stats]

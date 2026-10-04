# LangChain API-агент (OtusAI3) — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Минимальный AI-агент на LangChain (LangGraph `create_react_agent` + Ollama qwen2.5:3b) — естественный язык поверх HTTP API управления пользователями (FastAPI in-memory, поиск/правка по имени).

**Architecture:** Два процесса: FastAPI (порт 8001, in-memory store) и CLI `python main.py "<запрос>"`. Агент через 5 LangChain tools делает реальные HTTP-вызовы (httpx) к API, возвращает ответ в фиксированном контракте `Status/Action/Data/Errors`. Спека: `docs/superpowers/specs/2026-10-04-langchain-api-agent-design.md`.

**Tech Stack:** Python 3.13, langchain/langgraph/langchain-ollama, fastapi+uvicorn, httpx, pydantic-settings, pytest, ruff. Менеджер окружения: uv (как в прошлом проекте), фолбэк — venv+pip.

**Все команды выполняются в `P:\OtusAI3` (workdir). PowerShell 5.1.**

---

### Task 1: Каркас проекта

**Files:**
- Create: `pyproject.toml`, `.gitignore`, `.env.example`

- [ ] **Step 1: Создать `pyproject.toml`**

```toml
[project]
name = "api-agent"
version = "0.1.0"
description = "Минимальный LangChain-агент: естественный язык поверх HTTP API пользователей"
requires-python = ">=3.11"
dependencies = [
    "langchain>=0.3",
    "langgraph>=0.2",
    "langchain-ollama>=0.2",
    "fastapi>=0.115",
    "uvicorn>=0.30",
    "httpx>=0.27",
    "pydantic>=2.7",
    "pydantic-settings>=2.3",
]

[dependency-groups]
dev = [
    "pytest>=8",
    "ruff>=0.5",
]

[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[tool.hatch.build.targets.wheel]
packages = ["src/api_agent"]

[tool.ruff]
line-length = 100
src = ["src", "tests"]

[tool.ruff.lint]
select = ["E", "F", "I", "UP", "B"]

[tool.pytest.ini_options]
testpaths = ["tests"]
```

- [ ] **Step 2: Создать `.gitignore`**

```gitignore
.venv/
__pycache__/
*.pyc
.env
agent.log
.pytest_cache/
.ruff_cache/
*.egg-info/
dist/
build/
```

- [ ] **Step 3: Создать `.env.example`**

```
# Скопируйте в .env и при необходимости поправьте. Секретов нет: Ollama локальная.
AGENT_LLM_MODEL=qwen2.5:3b
AGENT_OLLAMA_BASE_URL=http://localhost:11434
AGENT_API_BASE_URL=http://localhost:8001
```

- [ ] **Step 4: Создать окружение и установить зависимости**

Проверить uv: `uv --version`.
- Если uv есть: `uv venv; uv sync`
- Иначе: `python -m venv .venv; .\.venv\Scripts\pip install -e .; .\.venv\Scripts\pip install pytest ruff`

Ожидание: успешная установка без ошибок.

- [ ] **Step 5: Создать пустые пакеты**

`src/api_agent/__init__.py` (пустой), `src/api_agent/api/__init__.py` (пустой), `src/api_agent/tools/__init__.py` (пустой), `tests/__init__.py` (пустой). Затем: `.\.venv\Scripts\python -c "import api_agent; print('ok')"` — ожидание: `ok`.

- [ ] **Step 6: Commit**

```powershell
git add pyproject.toml .gitignore .env.example src tests uv.lock
git commit -m "feat: каркас проекта (pyproject, src-layout, env)"
```

(если uv не использовался, `uv.lock` не добавлять)

---

### Task 2: In-memory хранилище пользователей (store)

**Files:**
- Create: `src/api_agent/api/store.py`
- Test: `tests/test_store.py`

- [ ] **Step 1: Написать проваливающийся тест `tests/test_store.py`**

```python
from api_agent.api.store import UserStore


def test_create_and_duplicate():
    s = UserStore()
    u, dup = s.create("Alex", None)
    assert u["name"] == "Alex"
    assert u["status"] == "active"
    assert u["id"] == 1
    assert dup is False
    _, dup2 = s.create("Alex", None)
    assert dup2 is True


def test_find_by_name():
    s = UserStore()
    s.create("Bob", None)
    s.create("Bob", None)
    assert len(s.find_by_name("Bob")) == 2
    assert s.find_by_name("Nope") == []


def test_update_status_single_and_ambiguous():
    s = UserStore()
    s.create("Carl", None)
    updated = s.update_status("Carl", "blocked")
    assert updated["status"] == "blocked"
    s.create("Carl", None)
    assert s.update_status("Carl", "active") is None


def test_stats():
    s = UserStore()
    s.create("A", None)
    s.create("B", None)
    s.update_status("B", "blocked")
    assert s.stats() == {"total": 2, "active": 1, "blocked": 1}


def test_reset():
    s = UserStore()
    s.create("X", None)
    s.reset()
    assert s.stats()["total"] == 0
```

- [ ] **Step 2: Запустить, убедиться в провале**

`.\.venv\Scripts\python -m pytest tests/test_store.py -v`
Ожидание: FAIL — `ModuleNotFoundError: No module named 'api_agent.api.store'` (или ImportError).

- [ ] **Step 3: Реализовать `src/api_agent/api/store.py`**

```python
from datetime import UTC, datetime
from threading import Lock


class UserStore:
    """Потокобезопасное in-memory хранилище пользователей."""

    def __init__(self) -> None:
        self._users: dict[int, dict] = {}
        self._next_id = 1
        self._lock = Lock()

    def create(self, name: str, email: str | None) -> tuple[dict, bool]:
        with self._lock:
            duplicate = any(u["name"] == name for u in self._users.values())
            user = {
                "id": self._next_id,
                "name": name,
                "email": email,
                "status": "active",
                "created_at": datetime.now(UTC).isoformat(),
            }
            self._users[self._next_id] = user
            self._next_id += 1
            return dict(user), duplicate

    def find_by_name(self, name: str) -> list[dict]:
        with self._lock:
            return [dict(u) for u in self._users.values() if u["name"] == name]

    def update_status(self, name: str, status: str) -> dict | None:
        with self._lock:
            matches = [u for u in self._users.values() if u["name"] == name]
            if len(matches) != 1:
                return None
            matches[0]["status"] = status
            return dict(matches[0])

    def all(self) -> list[dict]:
        with self._lock:
            return [dict(u) for u in self._users.values()]

    def stats(self) -> dict:
        with self._lock:
            users = list(self._users.values())
        return {
            "total": len(users),
            "active": sum(1 for u in users if u["status"] == "active"),
            "blocked": sum(1 for u in users if u["status"] == "blocked"),
        }

    def reset(self) -> None:
        with self._lock:
            self._users.clear()
            self._next_id = 1
```

- [ ] **Step 4: Прогнать тест — PASS**

`.\.venv\Scripts\python -m pytest tests/test_store.py -v`
Ожидание: 5 passed.

- [ ] **Step 5: Commit**

```powershell
git add src/api_agent/api/store.py tests/test_store.py
git commit -m "feat: in-memory хранилище пользователей с дубликатами имён"
```

---

### Task 3: FastAPI endpoints

**Files:**
- Create: `src/api_agent/api/app.py`
- Test: `tests/test_api.py`
- Create: `tests/conftest.py`

- [ ] **Step 1: Создать `tests/conftest.py` (сброс store между тестами)**

```python
import pytest

from api_agent.api.app import store


@pytest.fixture(autouse=True)
def reset_store():
    store.reset()
    yield
```

- [ ] **Step 2: Написать проваливающийся тест `tests/test_api.py`**

```python
from fastapi.testclient import TestClient

from api_agent.api.app import app

client = TestClient(app)


def test_create_user_201_and_duplicate_flag():
    r1 = client.post("/users", json={"name": "Alex"})
    assert r1.status_code == 201
    body = r1.json()
    assert body["name"] == "Alex"
    assert body["status"] == "active"
    assert body["duplicate"] is False
    r2 = client.post("/users", json={"name": "Alex"})
    assert r2.status_code == 201
    assert r2.json()["duplicate"] is True


def test_create_user_empty_name_422():
    r = client.post("/users", json={"name": ""})
    assert r.status_code == 422


def test_create_user_slash_in_name_422():
    r = client.post("/users", json={"name": "a/b"})
    assert r.status_code == 422


def test_get_by_name_found_and_404():
    client.post("/users", json={"name": "Bob"})
    r = client.get("/users/Bob")
    assert r.status_code == 200
    assert [u["name"] for u in r.json()] == ["Bob"]
    assert client.get("/users/Nobody").status_code == 404


def test_patch_status_success_409_404():
    client.post("/users", json={"name": "Carl"})
    r = client.patch("/users/Carl/status", json={"status": "blocked"})
    assert r.status_code == 200
    assert r.json()["status"] == "blocked"

    client.post("/users", json={"name": "Carl"})
    r = client.patch("/users/Carl/status", json={"status": "active"})
    assert r.status_code == 409
    assert "users" in r.json()["detail"]

    assert client.patch("/users/Ghost/status", json={"status": "blocked"}).status_code == 404


def test_patch_invalid_status_422():
    client.post("/users", json={"name": "Dan"})
    r = client.patch("/users/Dan/status", json={"status": "deleted"})
    assert r.status_code == 422


def test_stats():
    client.post("/users", json={"name": "A"})
    client.post("/users", json={"name": "B"})
    client.patch("/users/B/status", json={"status": "blocked"})
    assert client.get("/stats").json() == {"total": 2, "active": 1, "blocked": 1}


def test_list_users():
    client.post("/users", json={"name": "Ann"})
    r = client.get("/users")
    assert [u["name"] for u in r.json()] == ["Ann"]
```

- [ ] **Step 3: Запустить — провал**

`.\.venv\Scripts\python -m pytest tests/test_api.py -v`
Ожидание: FAIL (нет модуля `api_agent.api.app`).

- [ ] **Step 4: Реализовать `src/api_agent/api/app.py`**

```python
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field, field_validator

from .store import UserStore

app = FastAPI(title="Users API", version="0.1.0")
store = UserStore()

VALID_STATUSES = {"active", "blocked"}


class CreateUserIn(BaseModel):
    name: str = Field(min_length=1)
    email: str | None = None

    @field_validator("name")
    @classmethod
    def reject_slash(cls, v: str) -> str:
        # '/' запрещён: имя адресуется через path-параметр, %2F декодируется
        # до маршрутизации и имя становится недостижимым.
        if "/" in v:
            raise ValueError("имя не может содержать символ '/'")
        return v


class UpdateStatusIn(BaseModel):
    status: str


@app.post("/users", status_code=201)
def create_user(payload: CreateUserIn) -> dict:
    user, duplicate = store.create(payload.name, payload.email)
    return {**user, "duplicate": duplicate}


@app.get("/users")
def list_users() -> list[dict]:
    return store.all()


@app.get("/users/{name}")
def get_user_by_name(name: str) -> list[dict]:
    matches = store.find_by_name(name)
    if not matches:
        raise HTTPException(status_code=404, detail=f"пользователь '{name}' не найден")
    return matches


@app.patch("/users/{name}/status")
def update_user_status(name: str, payload: UpdateStatusIn) -> dict:
    if payload.status not in VALID_STATUSES:
        raise HTTPException(
            status_code=422, detail="status должен быть 'active' или 'blocked'"
        )
    matches = store.find_by_name(name)
    if not matches:
        raise HTTPException(status_code=404, detail=f"пользователь '{name}' не найден")
    if len(matches) > 1:
        raise HTTPException(
            status_code=409,
            detail={"message": f"имя '{name}' неоднозначно", "users": matches},
        )
    updated = store.update_status(name, payload.status)
    if updated is None:
        # Гонка: между find_by_name и update_status появился дубликат имени.
        raise HTTPException(
            status_code=409,
            detail={"message": f"имя '{name}' неоднозначно", "users": store.find_by_name(name)},
        )
    return updated


@app.get("/stats")
def get_stats() -> dict:
    return store.stats()
```

- [ ] **Step 5: Прогнать — PASS**

`.\.venv\Scripts\python -m pytest tests/test_api.py -v`
Ожидание: 8 passed.

- [ ] **Step 6: Smoke — поднять сервер вручную и стукнуться**

```powershell
Start-Process .\.venv\Scripts\python -ArgumentList "-m","uvicorn","api_agent.api.app:app","--port","8001"
Start-Sleep 3
Invoke-RestMethod http://localhost:8001/stats
```

Ожидание: `total active blocked` = `0 0 0`. Остановить процесс uvicorn.

- [ ] **Step 7: Commit**

```powershell
git add src/api_agent/api/app.py tests/test_api.py tests/conftest.py
git commit -m "feat: FastAPI users-API (create/get-by-name/patch-status/list/stats)"
```

---

### Task 4: Конфигурация (.env)

**Files:**
- Create: `src/api_agent/config.py`
- Test: `tests/test_config.py`

- [ ] **Step 1: Проваливающийся тест `tests/test_config.py`**

```python
from api_agent.config import get_settings


def test_env_overrides_defaults(monkeypatch):
    monkeypatch.setenv("AGENT_API_BASE_URL", "http://example:1234")
    get_settings.cache_clear()
    s = get_settings()
    assert s.api_base_url == "http://example:1234"
    assert s.llm_model == "qwen2.5:3b"
    assert s.ollama_base_url == "http://localhost:11434"
    get_settings.cache_clear()
```

- [ ] **Step 2: Провал**

`.\.venv\Scripts\python -m pytest tests/test_config.py -v` — FAIL (нет модуля config).

- [ ] **Step 3: Реализовать `src/api_agent/config.py`**

```python
from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="AGENT_", env_file=".env", extra="ignore"
    )

    llm_model: str = "qwen2.5:3b"
    ollama_base_url: str = "http://localhost:11434"
    api_base_url: str = "http://localhost:8001"


@lru_cache
def get_settings() -> Settings:
    return Settings()
```

- [ ] **Step 4: PASS**

`.\.venv\Scripts\python -m pytest tests/test_config.py -v` — 1 passed.

- [ ] **Step 5: Commit**

```powershell
git add src/api_agent/config.py tests/test_config.py
git commit -m "feat: конфигурация через pydantic-settings (.env)"
```

---

### Task 5: LangChain tools (реальные HTTP-вызовы + debug-лог)

**Files:**
- Create: `src/api_agent/tools/api_tools.py`
- Test: `tests/test_tools.py`
- Modify: `tests/conftest.py` (добавить fixtures: живой uvicorn-сервер и api_url)

- [ ] **Step 1: Дополнить `tests/conftest.py`** (полный новый вид файла)

```python
import threading
import time

import httpx
import pytest
import uvicorn

from api_agent.api.app import app, store
from api_agent.config import get_settings

API_PORT = 8977
API_URL = f"http://127.0.0.1:{API_PORT}"


@pytest.fixture(autouse=True)
def reset_store():
    store.reset()
    yield


@pytest.fixture(autouse=True)
def clear_settings_cache():
    yield
    get_settings.cache_clear()


@pytest.fixture(scope="session")
def api_server():
    config = uvicorn.Config(app, host="127.0.0.1", port=API_PORT, log_level="warning")
    server = uvicorn.Server(config)
    thread = threading.Thread(target=server.run, daemon=True)
    thread.start()
    for _ in range(50):
        try:
            httpx.get(f"{API_URL}/stats", timeout=0.5)
            break
        except httpx.HTTPError:
            time.sleep(0.1)
    yield server
    server.should_exit = True


@pytest.fixture()
def api_url(monkeypatch):
    monkeypatch.setenv("AGENT_API_BASE_URL", API_URL)
    get_settings.cache_clear()
    yield API_URL
    get_settings.cache_clear()
```

- [ ] **Step 2: Проваливающийся тест `tests/test_tools.py`**

```python
import json

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


def test_name_with_special_chars_roundtrip(api_server, api_url):
    parsed = _parse(create_user.invoke({"name": "a?b c"}))
    assert parsed["status"] == "success"
    found = _parse(get_users_by_name.invoke({"name": "a?b c"}))
    assert found["status"] == "success"
    assert found["data"][0]["name"] == "a?b c"


def test_create_name_with_slash_returns_422(api_server, api_url):
    parsed = _parse(create_user.invoke({"name": "a/b"}))
    assert parsed["status"] == "error"
    assert parsed["http_status"] == 422


def test_connection_error_returns_structured_error(api_server, monkeypatch):
    monkeypatch.setenv("AGENT_API_BASE_URL", "http://127.0.0.1:9")
    get_settings.cache_clear()
    parsed = _parse(list_users.invoke({}))
    assert parsed["status"] == "error"
    assert parsed["http_status"] is None
    assert "connection" in parsed["errors"].lower()
    get_settings.cache_clear()
```

Примечание: в начале файла тестов импорт `get_settings` — добавить `from api_agent.config import get_settings` в тест `test_connection_error_returns_structured_error` (локально в функции) — см. готовый код в шаге 2: строка `from api_agent.config import get_settings` уже включена в conftest; в test_tools.py для cache_clear нужен тот же импорт — добавить в начало файла: `from api_agent.config import get_settings`.

Итоговый список импортов в `tests/test_tools.py` (сверху):

```python
import json

from api_agent.config import get_settings
from api_agent.tools.api_tools import (
    create_user,
    get_user_stats,
    get_users_by_name,
    list_users,
    update_user_status_by_name,
)
```

- [ ] **Step 3: Провал**

`.\.venv\Scripts\python -m pytest tests/test_tools.py -v` — FAIL (нет api_tools).

- [ ] **Step 4: Реализовать `src/api_agent/tools/api_tools.py`**

```python
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
    return _request("GET", f"/users/{quote(name, safe='')}")


@tool
def update_user_status_by_name(name: str, status: str) -> str:
    """Изменить статус пользователя ('active' или 'blocked') по имени.

    Работает только если пользователь с таким именем ровно один.
    """
    return _request("PATCH", f"/users/{quote(name, safe='')}/status", json={"status": status})


@tool
def list_users() -> str:
    """Получить список всех пользователей."""
    return _request("GET", "/users")


@tool
def get_user_stats() -> str:
    """Получить статистику: сколько всего, активных и заблокированных пользователей."""
    return _request("GET", "/stats")


API_TOOLS = [create_user, get_users_by_name, update_user_status_by_name, list_users, get_user_stats]
```

- [ ] **Step 5: PASS**

`.\.venv\Scripts\python -m pytest tests/test_tools.py -v` — 7 passed.

- [ ] **Step 6: Полный прогон**

`.\.venv\Scripts\python -m pytest -v` — 21 passed (5 store + 8 api + 1 config + 7 tools).

- [ ] **Step 7: Commit**

```powershell
git add src/api_agent/tools/api_tools.py tests/test_tools.py tests/conftest.py
git commit -m "feat: 5 LangChain tools с реальными HTTP-вызовами и debug-логом"
```

---

### Task 6: Системный промпт и агент

**Files:**
- Create: `src/api_agent/prompts.py`, `src/api_agent/agent.py`
- Test: `tests/test_agent.py`

- [ ] **Step 1: Создать `src/api_agent/prompts.py`**

```python
SYSTEM_PROMPT = """Ты — оператор API управления пользователями.

ТВОИ ВОЗМОЖНОСТИ (только через доступные инструменты):
- создать пользователя (create_user);
- найти пользователей по имени (get_users_by_name);
- изменить статус пользователя active/blocked (update_user_status_by_name);
- показать всех пользователей (list_users);
- показать статистику (get_user_stats).

ПРАВИЛА:
1. Выполняй операции ТОЛЬКО через инструменты. Все данные бери из результата инструмента, ничего не выдумывай.
2. Если обязательного параметра нет (например, имя пользователя), задай уточняющий вопрос и НЕ вызывай инструмент. Такой ответ оформляй: Status: error, вопрос — в Errors.
3. Если запрошена неподдерживаемая операция (например, удаление), откажись: Status: error и описание в Errors. Инструмент не вызывай.
4. Если инструмент вернул duplicate=true или ошибку 409 (несколько пользователей с таким именем), обязательно сообщи об этом в Errors или Action.
5. Если инструмент вернул status=error, поставь Status: error и передай ошибку в Errors.

ФОРМАТ ОТВЕТА — строго, без лишних строк:
Status: success | error
Action: <краткое описание выполненного действия>
Data: <JSON из результата инструмента или null>
Errors: <пусто или описание ошибки>

ПРИМЕР ОТВЕТА:
Status: success
Action: Создан пользователь Alex
Data: {"id": 1, "name": "Alex", "email": null, "status": "active", "created_at": "2026-10-04T12:00:00+00:00", "duplicate": false}
Errors:

ПРИМЕР ОТВЕТА С ОШИБКОЙ:
Status: error
Action: Поиск пользователя Ghost
Data: null
Errors: пользователь 'Ghost' не найден (HTTP 404)
"""
```

- [ ] **Step 2: Проваливающийся smoke-тест `tests/test_agent.py`**

```python
from api_agent.agent import build_agent


def test_build_agent_returns_invokable_graph():
    agent = build_agent()
    assert callable(agent.invoke)
```

- [ ] **Step 3: Провал, затем реализовать `src/api_agent/agent.py`**

Провал: `.\.venv\Scripts\python -m pytest tests/test_agent.py -v` (нет модуля agent).

```python
from langchain_ollama import ChatOllama
from langgraph.prebuilt import create_react_agent

from .config import get_settings
from .prompts import SYSTEM_PROMPT
from .tools.api_tools import API_TOOLS


def build_agent():
    settings = get_settings()
    model = ChatOllama(
        model=settings.llm_model,
        base_url=settings.ollama_base_url,
        temperature=0,
    )
    return create_react_agent(model, API_TOOLS, prompt=SYSTEM_PROMPT)
```

(ChatOllama не ходит в сеть при инициализации; create_react_agent валидирует tools локально.)

- [ ] **Step 4: PASS**

`.\.venv\Scripts\python -m pytest tests/test_agent.py -v` — 1 passed.

- [ ] **Step 5: Commit**

```powershell
git add src/api_agent/prompts.py src/api_agent/agent.py tests/test_agent.py
git commit -m "feat: системный промпт и сборка create_react_agent"
```

---

### Task 7: CLI

**Files:**
- Create: `src/api_agent/cli.py`, `main.py` (в корне)
- Test: `tests/test_cli.py`

- [ ] **Step 1: Проваливающийся тест `tests/test_cli.py`**

```python
from api_agent.cli import is_contract_answer


def test_contract_answer_accepted():
    assert is_contract_answer("Status: success\nAction: создан")
    assert is_contract_answer("  Status: error\nAction: нет")


def test_raw_answer_rejected():
    assert not is_contract_answer("Готово! Пользователь создан.")
    assert not is_contract_answer("")
```

- [ ] **Step 2: Провал** — `.\.venv\Scripts\python -m pytest tests/test_cli.py -v` (нет модуля cli).

- [ ] **Step 3: Реализовать `src/api_agent/cli.py`**

```python
import logging
import sys

from .agent import build_agent

logger = logging.getLogger("api_agent.cli")


def is_contract_answer(text: str) -> bool:
    return text.lstrip().startswith("Status:")


def run(query: str) -> str:
    agent = build_agent()
    result = agent.invoke({"messages": [{"role": "user", "content": query}]})
    return str(result["messages"][-1].content)


def main() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(name)s %(levelname)s %(message)s",
        handlers=[
            logging.StreamHandler(),
            logging.FileHandler("agent.log", encoding="utf-8"),
        ],
    )
    if len(sys.argv) < 2 or not sys.argv[1].strip():
        print('Использование: python main.py "<запрос на естественном языке>"')
        raise SystemExit(1)
    answer = run(sys.argv[1])
    print(answer if is_contract_answer(answer) else f"[raw] {answer}")
```

- [ ] **Step 4: Создать `main.py` в корне**

```python
from api_agent.cli import main

if __name__ == "__main__":
    main()
```

- [ ] **Step 5: PASS + smoke без аргументов**

`.\.venv\Scripts\python -m pytest tests/test_cli.py -v` — 2 passed.
`.\.venv\Scripts\python main.py` — ожидание: строка «Использование: ...», exit code 1.

- [ ] **Step 6: Commit**

```powershell
git add src/api_agent/cli.py main.py tests/test_cli.py
git commit -m "feat: CLI-точка входа с проверкой контракта ответа"
```

---

### Task 8: Документация (README, промпты, каркас отчёта)

**Files:**
- Create: `README.md`, `docs/prompts.md`, `report.md`

- [ ] **Step 1: `README.md`**

````markdown
# API-агент на LangChain (OtusAI3)

Минимальный AI-агент — натурально-языковая обёртка над HTTP API управления
пользователями. Задание курса Otus «Минимальный агент на LangChain».

## Стек
- LLM: Ollama, модель `qwen2.5:3b` (локально, ключи не нужны)
- Агент: LangChain + LangGraph `create_react_agent`
- API: FastAPI (в этом же репозитории, in-memory)

## Настройка
1. Python 3.11+
2. Установить [Ollama](https://ollama.com), затем:
   `ollama pull qwen2.5:3b`
3. Окружение:
   - uv: `uv venv; uv sync`
   - или: `python -m venv .venv; .\.venv\Scripts\pip install -e .; .\.venv\Scripts\pip install pytest ruff`
4. `Copy-Item .env.example .env` (при необходимости поправьте)

## Запуск (два терминала)
Терминал 1 — API:
```powershell
.\.venv\Scripts\python -m uvicorn api_agent.api.app:app --port 8001
```

Терминал 2 — агент:
```powershell
.\.venv\Scripts\python main.py "создай пользователя с именем Alex"
```

## Операции API
| Метод | Endpoint | Описание |
|---|---|---|
| POST | `/users` `{name, email?}` | создать; `duplicate: true` если имя уже было; `/` в имени запрещён (422) |
| GET | `/users/{name}` | список совпадений; 404 если пусто |
| PATCH | `/users/{name}/status` `{status}` | 200 если имя уникально; 409 если несколько; 404 если нет |
| GET | `/users` | все пользователи |
| GET | `/stats` | `{total, active, blocked}` |

## Контракт ответа агента
```
Status: success | error
Action: <описание действия>
Data: <JSON-результат API или null>
Errors: <пусто | описание ошибки>
```
Требования к формату зафиксированы здесь (раздел «Контракт ответа агента») и в
`docs/prompts.md` (системный промпт, строки с «ФОРМАТ ОТВЕТА»).

## Где что искать (для проверки)
- Объявление tools и реальные HTTP-вызовы: `src/api_agent/tools/api_tools.py`
  (tools `create_user`, `get_users_by_name`, `update_user_status_by_name`,
  `list_users`, `get_user_stats`; HTTP — `client.request(...)` внутри `_request`).
  Точные диапазоны строк см. в `report.md` (раздел «Карта кода»).
- Debug-вывод результата tool: `logger.info("tool result: ...")` в
  `src/api_agent/tools/api_tools.py` (функции `_result` и `_request`) —
  выводится в консоль и в `agent.log`.
- Системный промпт: `src/api_agent/prompts.py`, копия — `docs/prompts.md`.

## Тесты
```powershell
.\.venv\Scripts\python -m pytest -v
```

## Отчёт
Результаты проверки — `report.md`. Использованные промпты — `docs/prompts.md`.
````

- [ ] **Step 2: `docs/prompts.md`**

````markdown
# Использованные промпты

## Системный промпт
Источник: `src/api_agent/prompts.py` (переменная `SYSTEM_PROMPT`).

```text
<полный текст SYSTEM_PROMPT из src/api_agent/prompts.py — скопировать 1:1>
```

## Пользовательские шаблоны запросов
1. Создание: «создай пользователя с именем {имя}» (опционально: «с email {email}»)
2. Поиск: «найди пользователя {имя}» / «покажи данные пользователя {имя}»
3. Смена статуса: «заблокируй пользователя {имя}» / «разблокируй пользователя {имя}»
4. Статистика: «сколько всего пользователей и сколько активных?»
5. Вне возможностей: «удали пользователя {имя}» (ожидается отказ)

## Пример соответствия запрос → метод API
- «создай пользователя с именем Alex» → tool `create_user` → `POST /users`
- «заблокируй пользователя Alex» → tool `update_user_status_by_name` → `PATCH /users/Alex/status`
````

- [ ] **Step 3: Каркас `report.md`**

```markdown
# Отчёт: минимальный агент на LangChain

## LLM
Ollama, модель qwen2.5:3b, http://localhost:11434. Настройка — см. README («Настройка»).
Секретов нет (локальная LLM); конфигурация через .env (см. .env.example).

## API
FastAPI в этом же репозитории (in-memory), операции: create / get-by-name /
patch-status / list / stats — см. README («Операции API»).

## Запуск
См. README («Запуск»): uvicorn (порт 8001) + `python main.py "<запрос>"`.

## Карта кода (для критериев проверки)
- tool-объявления: src/api_agent/tools/api_tools.py, строки X–Y
- реальный HTTP-вызов: src/api_agent/tools/api_tools.py, строки X–Y (client.request)
- debug-вывод результата tool: src/api_agent/tools/api_tools.py, строки X–Y (logger.info)
- контракт ответа: README.md (раздел «Контракт ответа агента»), docs/prompts.md

## Проверочные запросы (5)
(заполняется фактическими выводами на шаге ручной проверки)

### 1. «Создай пользователя с именем Alex» → ожидание: POST /users
…
### 2. «Найди пользователя Alex» → ожидание: GET /users/Alex
…
### 3. «Заблокируй пользователя Alex» → ожидание: PATCH /users/Alex/status
…
### 4. «Сколько всего пользователей и сколько активных?» → ожидание: GET /stats
…
### 5. «Удали пользователя Alex» → ожидание: отказ без вызова API
…
```

- [ ] **Step 4: Commit**

```powershell
git add README.md docs/prompts.md report.md
git commit -m "docs: README, список промптов, каркас отчёта"
```

---

### Task 9: Ручная проверка (обязательная) и финальный отчёт

**Files:**
- Modify: `report.md`, `README.md` (диапазоны строк при необходимости)

- [ ] **Step 1: Проверить Ollama**

`ollama list` — модель `qwen2.5:3b` должна быть в списке; иначе `ollama pull qwen2.5:3b`.

- [ ] **Step 2: Поднять API**

Терминал: `.\.venv\Scripts\python -m uvicorn api_agent.api.app:app --port 8001` — оставить работать.

- [ ] **Step 3: Выполнить 5 запросов, сохранив вывод**

В отдельном терминале, каждый — с чистым состоянием API (перезапуск uvicorn между группами при необходимости):
1. `.\.venv\Scripts\python main.py "создай пользователя с именем Alex"`
2. `.\.venv\Scripts\python main.py "найди пользователя Alex"`
3. `.\.venv\Scripts\python main.py "заблокируй пользователя Alex"`
4. `.\.venv\Scripts\python main.py "сколько всего пользователей и сколько активных?"`
5. `.\.venv\Scripts\python main.py "удали пользователя Alex"`

Ожидания: 1 → POST /users (лог `tool result:` с http_status 201); 2 → GET /users/Alex; 3 → PATCH /users/Alex/status; 4 → GET /stats; 5 → Status: error, отказ, НЕТ вызова tool в логе.
Каждый вывод (ответ агента + строка лога `api_agent.tools ... tool result:` из консоли/agent.log) вставить в `report.md`.

- [ ] **Step 4: Заполнить «Карту кода» в report.md**

Определить фактические диапазоны строк в `src/api_agent/tools/api_tools.py` (объявления `@tool`, `client.request`, `logger.info`) и заменить X–Y. Проверить, что README ссылается корректно.

- [ ] **Step 5: Финальные проверки**

- `.\.venv\Scripts\python -m pytest -v` — все passed (24)
- `.\.venv\Scripts\python -m ruff check .` — без ошибок
- `git status` — `.env` и `agent.log` не отслеживаются; убедиться, что нигде нет ключей (их и не должно быть)

- [ ] **Step 6: Commit**

```powershell
git add report.md README.md
git commit -m "docs: отчёт с 5 проверочными запросами и картой кода"
```

---

## Самопроверка плана (выполнено при написании)

- Покрытие спеки: каркас (T1), store (T2), API+контракт dup/409 (T3), config (T4), tools+debug-лог (T5), промпт+агент (T6), CLI+контракт+[raw] (T7), README/prompts/report (T8), 5 запросов+карта кода (T9). Разделы спеки 3–15 закрыты.
- Типы/имена: `UserStore.create→tuple[dict,bool]`, `update_status→dict|None`, tools имена совпадают в T5/T6 (`API_TOOLS`), `get_settings` кэш очищается в тестах, `is_contract_answer` одинаковый в T7.
- Плейсхолдеров в коде нет; «X–Y» встречается только в report.md как явное действие «определить фактические строки» (Task 9 Step 4).

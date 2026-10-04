# Каталог книг на SQLite — Implementation Plan (итерация 2)

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Заменить домен «пользователи» на каталог книг (название уникально) с хранением в SQLite; операции add / get / rename / delete / list / stats через тех же LangChain tools и агента.

**Architecture:** Без изменений против итерации 1 (CLI → LangGraph-агент → tools → httpx → FastAPI), меняются: хранилище (SQLite вместо dict), роуты (/books), tools (6 шт.), промпт, документация. Спека: `docs/superpowers/specs/2026-10-04-books-catalog-sqlite-design.md`.

**Tech Stack:** как ранее + stdlib `sqlite3`. Новых зависимостей нет.

**Все команды в `P:\OtusAI3` (workdir), PowerShell 5.1. Тесты: `uv run python -m pytest -v`.**

Итоговое число тестов после всех задач: 30 (store 10, api 8, config 2, tools 7, agent 1, cli 2).

---

### Task B1: Конфигурация — AGENT_DB_PATH

**Files:**
- Modify: `src/api_agent/config.py`, `tests/test_config.py`, `.env.example`, `.gitignore`, `pyproject.toml` (per-file-ignore E402 для conftest — задел под Task B3)

- [ ] **Step 1: Обновить тест `tests/test_config.py`** (полный новый вид):

```python
from api_agent.config import get_settings


def test_env_overrides_defaults(monkeypatch):
    monkeypatch.setenv("AGENT_API_BASE_URL", "http://example:1234")
    monkeypatch.setenv("AGENT_DB_PATH", "C:/tmp/x.db")
    get_settings.cache_clear()
    s = get_settings()
    assert s.api_base_url == "http://example:1234"
    assert s.db_path == "C:/tmp/x.db"
    assert s.llm_model == "qwen2.5:3b"
    assert s.ollama_base_url == "http://localhost:11434"
    get_settings.cache_clear()


def test_db_path_default():
    get_settings.cache_clear()
    s = get_settings()
    assert s.db_path == "books.db"
    get_settings.cache_clear()
```

- [ ] **Step 2: Провал** — `uv run python -m pytest tests/test_config.py -v` — FAIL (нет поля db_path).

- [ ] **Step 3: Обновить `src/api_agent/config.py`** (полный новый вид):

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
    db_path: str = "books.db"


@lru_cache
def get_settings() -> Settings:
    return Settings()
```

- [ ] **Step 4: PASS** — 2 passed.

- [ ] **Step 5: `.env.example`** — добавить строку в конец:

```
AGENT_DB_PATH=books.db
```

- [ ] **Step 6: `.gitignore`** — добавить:

```
books.db
.test-books.db
```

- [ ] **Step 7: `pyproject.toml`** — секция per-file-ignores принимает вид:

```toml
[tool.ruff.lint.per-file-ignores]
"src/api_agent/prompts.py" = ["E501"]
"tests/conftest.py" = ["E402"]
```

- [ ] **Step 8: Commit**

```powershell
git add src/api_agent/config.py tests/test_config.py .env.example .gitignore pyproject.toml
git commit -m "feat: настройка AGENT_DB_PATH для SQLite-хранилища"
```

---

### Task B2: BookStore на SQLite (TDD)

**Files:**
- Replace: `src/api_agent/api/store.py` (полная замена UserStore → BookStore)
- Replace: `tests/test_store.py`

- [ ] **Step 1: Заменить `tests/test_store.py`** (полный новый вид):

```python
import pytest

from api_agent.api.store import BookStore, ConflictError, NotFoundError


@pytest.fixture()
def s(tmp_path):
    return BookStore(str(tmp_path / "books.db"))


def test_add_and_find(s):
    book = s.add("Мастер и Маргарита")
    assert book["title"] == "Мастер и Маргарита"
    assert book["id"] == 1
    assert book["created_at"]
    assert s.find_by_title("Мастер и Маргарита") == book
    assert s.find_by_title("Нет такой") is None


def test_add_duplicate_raises_conflict(s):
    s.add("Война и мир")
    with pytest.raises(ConflictError):
        s.add("Война и мир")


def test_rename(s):
    s.add("Война и мир")
    renamed = s.rename("Война и мир", "Война и мир (сокращённая)")
    assert renamed["title"] == "Война и мир (сокращённая)"
    assert renamed["id"] == 1
    assert s.find_by_title("Война и мир") is None
    assert s.find_by_title("Война и мир (сокращённая)") is not None


def test_rename_not_found(s):
    with pytest.raises(NotFoundError):
        s.rename("Призрак", "Другое")


def test_rename_conflict(s):
    s.add("Книга А")
    s.add("Книга Б")
    with pytest.raises(ConflictError):
        s.rename("Книга А", "Книга Б")


def test_delete(s):
    s.add("Книга А")
    s.delete("Книга А")
    assert s.find_by_title("Книга А") is None
    assert s.stats() == {"total": 0}


def test_delete_not_found(s):
    with pytest.raises(NotFoundError):
        s.delete("Призрак")


def test_all_and_stats(s):
    s.add("Книга А")
    s.add("Книга Б")
    assert [b["title"] for b in s.all()] == ["Книга А", "Книга Б"]
    assert s.stats() == {"total": 2}


def test_reset_restarts_ids(s):
    s.add("Книга А")
    s.reset()
    assert s.stats() == {"total": 0}
    assert s.add("Книга Б")["id"] == 1


def test_persistence_across_instances(tmp_path):
    db = str(tmp_path / "books.db")
    BookStore(db).add("Пикник на обочине")
    second = BookStore(db)
    assert second.find_by_title("Пикник на обочине") is not None
```

- [ ] **Step 2: Провал** — `uv run python -m pytest tests/test_store.py -v` — FAIL (нет BookStore).

- [ ] **Step 3: Заменить `src/api_agent/api/store.py`** (полный новый вид):

```python
import sqlite3
from datetime import UTC, datetime

from ..config import get_settings


class NotFoundError(Exception):
    """Книга не найдена."""


class ConflictError(Exception):
    """Конфликт уникальности названия."""


_SCHEMA = """
CREATE TABLE IF NOT EXISTS books (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    title TEXT NOT NULL UNIQUE,
    created_at TEXT NOT NULL
)
"""


class BookStore:
    """Каталог книг в SQLite. Подключение открывается на каждую операцию."""

    def __init__(self, db_path: str = "") -> None:
        self._db_path = db_path
        self._init_schema()

    def _path(self) -> str:
        return self._db_path or get_settings().db_path

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self._path())
        conn.row_factory = sqlite3.Row
        return conn

    def _init_schema(self) -> None:
        with self._connect() as conn:
            conn.execute(_SCHEMA)

    @staticmethod
    def _book(row: sqlite3.Row) -> dict:
        return {"id": row["id"], "title": row["title"], "created_at": row["created_at"]}

    def add(self, title: str) -> dict:
        with self._connect() as conn:
            try:
                conn.execute(
                    "INSERT INTO books (title, created_at) VALUES (?, ?)",
                    (title, datetime.now(UTC).isoformat()),
                )
            except sqlite3.IntegrityError as exc:
                raise ConflictError(f"книга '{title}' уже есть в каталоге") from exc
            row = conn.execute(
                "SELECT * FROM books WHERE title = ?", (title,)
            ).fetchone()
        return self._book(row)

    def find_by_title(self, title: str) -> dict | None:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT * FROM books WHERE title = ?", (title,)
            ).fetchone()
        return self._book(row) if row else None

    def rename(self, title: str, new_title: str) -> dict:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT * FROM books WHERE title = ?", (title,)
            ).fetchone()
            if row is None:
                raise NotFoundError(f"книга '{title}' не найдена")
            try:
                conn.execute(
                    "UPDATE books SET title = ? WHERE id = ?", (new_title, row["id"])
                )
            except sqlite3.IntegrityError as exc:
                raise ConflictError(f"название '{new_title}' уже занято") from exc
            updated = conn.execute(
                "SELECT * FROM books WHERE id = ?", (row["id"],)
            ).fetchone()
        return self._book(updated)

    def delete(self, title: str) -> None:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT id FROM books WHERE title = ?", (title,)
            ).fetchone()
            if row is None:
                raise NotFoundError(f"книга '{title}' не найдена")
            conn.execute("DELETE FROM books WHERE id = ?", (row["id"],))

    def all(self) -> list[dict]:
        with self._connect() as conn:
            rows = conn.execute("SELECT * FROM books ORDER BY id").fetchall()
        return [self._book(r) for r in rows]

    def stats(self) -> dict:
        with self._connect() as conn:
            total = conn.execute("SELECT COUNT(*) FROM books").fetchone()[0]
        return {"total": total}

    def reset(self) -> None:
        with self._connect() as conn:
            conn.execute("DELETE FROM books")
            try:
                conn.execute("DELETE FROM sqlite_sequence WHERE name = 'books'")
            except sqlite3.OperationalError:
                pass  # sqlite_sequence ещё не создан (не было AUTOINCREMENT-вставок)
```

- [ ] **Step 4: PASS** — `uv run python -m pytest tests/test_store.py -v` — 10 passed. Полный прогон упадёт в test_api/test_tools (старые пользователи) — это ожидаемо, чинится в B3/B4.

- [ ] **Step 5: Commit**

```powershell
git add src/api_agent/api/store.py tests/test_store.py
git commit -m "feat: BookStore на SQLite вместо in-memory UserStore"
```

---

### Task B3: FastAPI /books (TDD)

**Files:**
- Replace: `src/api_agent/api/app.py`, `tests/test_api.py`, `tests/conftest.py`

- [ ] **Step 1: Заменить `tests/conftest.py`** (полный новый вид; env ДО импорта app):

```python
import os
import threading
import time

import httpx
import pytest
import uvicorn

os.environ["AGENT_DB_PATH"] = ".test-books.db"

from api_agent.api.app import app, store  # noqa: E402
from api_agent.config import get_settings  # noqa: E402

get_settings.cache_clear()

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

- [ ] **Step 2: Заменить `tests/test_api.py`** (полный новый вид):

```python
from fastapi.testclient import TestClient

from api_agent.api.app import app

client = TestClient(app)


def test_add_book_201():
    r = client.post("/books", json={"title": "Мастер и Маргарита"})
    assert r.status_code == 201
    body = r.json()
    assert body["title"] == "Мастер и Маргарита"
    assert body["id"] == 1
    assert body["created_at"]


def test_add_book_duplicate_409():
    client.post("/books", json={"title": "Война и мир"})
    r = client.post("/books", json={"title": "Война и мир"})
    assert r.status_code == 409


def test_add_book_invalid_422():
    assert client.post("/books", json={"title": ""}).status_code == 422
    assert client.post("/books", json={"title": "а/б"}).status_code == 422


def test_get_book_200_404():
    client.post("/books", json={"title": "Мы"})
    r = client.get("/books/Мы")
    assert r.status_code == 200
    assert r.json()["title"] == "Мы"
    assert client.get("/books/Призрак").status_code == 404


def test_rename_book_200_404_409():
    client.post("/books", json={"title": "Мы"})
    r = client.patch("/books/Мы", json={"new_title": "Мы (замятин)"})
    assert r.status_code == 200
    assert r.json()["title"] == "Мы (замятин)"

    assert client.patch("/books/Призрак", json={"new_title": "X"}).status_code == 404

    client.post("/books", json={"title": "Занято"})
    r = client.patch("/books/Мы (замятин)", json={"new_title": "Занято"})
    assert r.status_code == 409


def test_rename_invalid_422():
    client.post("/books", json={"title": "Мы"})
    assert client.patch("/books/Мы", json={"new_title": ""}).status_code == 422
    assert client.patch("/books/Мы", json={"new_title": "а/б"}).status_code == 422


def test_delete_book_204_404():
    client.post("/books", json={"title": "Мы"})
    r = client.delete("/books/Мы")
    assert r.status_code == 204
    assert r.content == b""
    assert client.get("/books/Мы").status_code == 404
    assert client.delete("/books/Мы").status_code == 404


def test_list_books_and_stats():
    client.post("/books", json={"title": "А"})
    client.post("/books", json={"title": "Б"})
    assert [b["title"] for b in client.get("/books").json()] == ["А", "Б"]
    client.delete("/books/А")
    assert client.get("/stats").json() == {"total": 1}
```

- [ ] **Step 3: Заменить `src/api_agent/api/app.py`** (полный новый вид):

```python
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field, field_validator

from .store import BookStore, ConflictError, NotFoundError

app = FastAPI(title="Books Catalog API", version="0.2.0")
store = BookStore()


def _reject_slash(v: str) -> str:
    # '/' запрещён: название адресуется через path-параметр
    if "/" in v:
        raise ValueError("название не может содержать символ '/'")
    return v


class BookTitleIn(BaseModel):
    title: str = Field(min_length=1)

    @field_validator("title")
    @classmethod
    def reject_slash(cls, v: str) -> str:
        return _reject_slash(v)


class NewTitleIn(BaseModel):
    new_title: str = Field(min_length=1)

    @field_validator("new_title")
    @classmethod
    def reject_slash(cls, v: str) -> str:
        return _reject_slash(v)


@app.post("/books", status_code=201)
def add_book(payload: BookTitleIn) -> dict:
    try:
        return store.add(payload.title)
    except ConflictError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@app.get("/books")
def list_books() -> list[dict]:
    return store.all()


@app.get("/books/{title}")
def get_book_by_title(title: str) -> dict:
    book = store.find_by_title(title)
    if book is None:
        raise HTTPException(status_code=404, detail=f"книга '{title}' не найдена")
    return book


@app.patch("/books/{title}")
def rename_book(title: str, payload: NewTitleIn) -> dict:
    try:
        return store.rename(title, payload.new_title)
    except NotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ConflictError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@app.delete("/books/{title}", status_code=204)
def delete_book(title: str) -> None:
    try:
        store.delete(title)
    except NotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@app.get("/stats")
def get_stats() -> dict:
    return store.stats()
```

- [ ] **Step 4: PASS** — `uv run python -m pytest tests/test_api.py -v` — 8 passed. Прогон `uv run python -m pytest tests/test_api.py tests/test_store.py tests/test_config.py tests/test_agent.py tests/test_cli.py -v` — 22 passed (test_tools ещё старый, чинится в B4).

- [ ] **Step 5: Smoke** — поднять uvicorn (порт 8001), `Invoke-RestMethod http://localhost:8001/stats` → `{"total":0,...}`, затем остановить. Убедиться, что в репо создался `books.db` (это ок, он в .gitignore).

- [ ] **Step 6: Commit**

```powershell
git add src/api_agent/api/app.py tests/test_api.py tests/conftest.py
git commit -m "feat: FastAPI каталога книг (/books, SQLite)"
```

---

### Task B4: Tools для каталога книг (TDD)

**Files:**
- Replace: `src/api_agent/tools/api_tools.py`, `tests/test_tools.py`

- [ ] **Step 1: Заменить `tests/test_tools.py`** (полный новый вид):

```python
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
```

(7 тестов; в счётчике выше tools=7 → итог 30)

- [ ] **Step 2: Провал** — `uv run python -m pytest tests/test_tools.py -v` (нет новых tool-функций).

- [ ] **Step 3: Заменить `src/api_agent/tools/api_tools.py`** (полный новый вид):

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
```

- [ ] **Step 4: PASS + полный прогон**

`uv run python -m pytest tests/test_tools.py -v` — 7 passed.
`uv run python -m pytest -v` — 30 passed. `uv run python -m ruff check .` — чисто.

- [ ] **Step 5: Commit**

```powershell
git add src/api_agent/tools/api_tools.py tests/test_tools.py
git commit -m "feat: 6 tools каталога книг с реальными HTTP-вызовами"
```

---

### Task B5: Промпт оператора каталога книг

**Files:**
- Replace: `src/api_agent/prompts.py`, `docs/prompts.md`

- [ ] **Step 1: Заменить `src/api_agent/prompts.py`** (полный новый вид):

```python
SYSTEM_PROMPT = """Ты — оператор каталога книг.

ТВОИ ВОЗМОЖНОСТИ (только через доступные инструменты):
- добавить книгу (add_book);
- найти книгу по названию (get_book_by_title);
- переименовать книгу (rename_book);
- удалить книгу (delete_book);
- показать все книги (list_books);
- показать статистику каталога (get_catalog_stats).

ПРАВИЛА:
1. Выполняй операции ТОЛЬКО через инструменты. Все данные бери из результата инструмента, ничего не выдумывай.
2. Если обязательного параметра нет (например, название книги), задай уточняющий вопрос и НЕ вызывай инструмент. Такой ответ оформляй: Status: error, вопрос — в Errors.
3. Если запрошена неподдерживаемая операция (например, выдать книгу читателю, указать автора), откажись: Status: error и описание в Errors. Инструмент не вызывай.
4. Если инструмент вернул ошибку 409 (название уже занято), обязательно сообщи об этом в Errors.
5. Если инструмент вернул status=error, поставь Status: error и передай ошибку в Errors.
6. На вопросы-подсчёты («сколько», «сколько всего книг») тоже отвечай строго по формату: Data — JSON статистики из инструмента, Action — краткий ответ словами.

ФОРМАТ ОТВЕТА — строго, без лишних строк:
Status: success | error
Action: <краткое описание выполненного действия>
Data: <JSON из результата инструмента или null>
Errors: <пусто или описание ошибки>

ПРИМЕР ОТВЕТА:
Status: success
Action: Добавлена книга «Мастер и Маргарита»
Data: {"id": 1, "title": "Мастер и Маргарита", "created_at": "2026-10-04T12:00:00+00:00"}
Errors:

ПРИМЕР ОТВЕТА С ОШИБКОЙ:
Status: error
Action: Поиск книги «Ghost»
Data: null
Errors: книга 'Ghost' не найдена (HTTP 404)

ПРИМЕР ОТВЕТА НА ВОПРОС «СКОЛЬКО»:
Status: success
Action: Получена статистика: всего 2 книги
Data: {"total": 2}
Errors:

НАПОМИНАНИЕ: каждый твой ответ НАЧИНАЕТСЯ со строки "Status:" и содержит ровно четыре строки: Status, Action, Data, Errors. Никакого текста вне формата, даже если вопрос простой.
"""
```

- [ ] **Step 2: `docs/prompts.md`** — тот же каркас, что был, но системный промпт заменить на текст выше (1:1) и обновить шаблоны:

```markdown
## Пользовательские шаблоны запросов
1. Добавление: «добавь книгу {название}»
2. Поиск: «найди книгу {название}»
3. Переименование: «переименуй книгу {старое название} в {новое название}»
4. Удаление: «удали книгу {название}»
5. Статистика: «сколько всего книг в каталоге?»
6. Вне возможностей: «выдай книгу {название} читателю {имя}» (ожидается отказ)

## Пример соответствия запрос → метод API
- «добавь книгу Мастер и Маргарита» → tool `add_book` → `POST /books`
- «удали книгу Война и мир» → tool `delete_book` → `DELETE /books/Война и мир`
```

- [ ] **Step 3: Проверки**

`uv run python -m pytest tests/test_agent.py -v` — 1 passed (промпт не ломает сборку агента).
`uv run python -m pytest -v` — 30 passed. `uv run python -m ruff check .` — чисто.
Сравнить промпт в docs/prompts.md с prompts.py (1:1).

- [ ] **Step 4: Commit**

```powershell
git add src/api_agent/prompts.py docs/prompts.md
git commit -m "feat: системный промпт оператора каталога книг"
```

---

### Task B6: Документация

**Files:**
- Replace: `README.md`, `report.md`

- [ ] **Step 1: Обновить `README.md`**: заголовок/описание — «Каталог книг: AI-агент на LangChain»; стек — добавить «Хранение: SQLite (файл из AGENT_DB_PATH)»; настройка — без изменений + `.env` с `AGENT_DB_PATH`; операции:

| Метод | Endpoint | Описание |
|---|---|---|
| POST | `/books` `{title}` | добавить; 409 если название занято; `/` в названии запрещён (422) |
| GET | `/books/{title}` | книга; 404 если нет |
| PATCH | `/books/{title}` `{new_title}` | переименовать; 404/409/422 |
| DELETE | `/books/{title}` | удалить; 204; 404 если нет |
| GET | `/books` | все книги |
| GET | `/stats` | `{"total": N}` |

Пример запуска: `python main.py "добавь книгу Мастер и Маргарита"`. Секции «Контракт ответа агента», «Где что искать» (tools-имена обновить на книжные; карта строк — в report.md), «Тесты», «Отчёт» — сохранить.

- [ ] **Step 2: `report.md`** — каркас как был (LLM/API/Запуск/Карта кода с X–Y/Проверочные запросы), обновить: описание API (книги, SQLite, 6 операций), разделы 6 запросов:

1. «Добавь книгу Мастер и Маргарита» → POST /books
2. «Найди книгу Мастер и Маргарита» → GET /books/…
3. «Переименуй книгу Мастер и Маргарита в Мастер и Маргарита (роман)» → PATCH /books/…
4. «Удали книгу Мастер и Маргарита (роман)» → DELETE /books/…
5. «Сколько всего книг в каталоге?» → GET /stats
6. «Выдай книгу Война и мир читателю Ивану» → отказ без вызова API

- [ ] **Step 3: Commit**

```powershell
git add README.md report.md
git commit -m "docs: README и каркас отчёта для каталога книг"
```

---

### Task B7: Ручная проверка (обязательная) и финальный отчёт

- [ ] **Step 1:** Убедиться: Ollama доступна (http://localhost:11434/api/version), uvicorn поднят на 8001 со свежей БД (при необходимости удалить books.db и перезапустить).

- [ ] **Step 2:** Выполнить 6 запросов из report.md (каждый с timeout=300000), зафиксировать ответы + строки лога `tool result`; для запроса 6 убедиться, что новых tool-вызовов нет.

- [ ] **Step 3:** Заполнить report.md: 6 разделов + «Наблюдения» + «Карта кода» (фактические строки: @tool-объявления, client.request, logger.info в api_tools.py; logging в cli.py; строка контракта в README).

- [ ] **Step 4:** `uv run python -m pytest -v` (30 passed), `uv run python -m ruff check .`, `git status` (books.db/.test-books.db/логи не отслеживаются).

- [ ] **Step 5:** Остановить uvicorn. Commit: `git add report.md; git commit -m "docs: отчёт каталога книг с 6 проверочными запросами"`

---

## Самопроверка плана

- Спека покрыта: B1 (§7), B2 (§3), B3 (§4), B4 (§5), B5 (§6), B6–B7 (§9–10).
- Имена согласованы: BookStore/NotFoundError/ConflictError; tools add_book/get_book_by_title/rename_book/delete_book/list_books/get_catalog_stats совпадают в B4/B5/README.
- Итоговое число тестов: store 10 + api 8 + config 2 + tools 7 + agent 1 + cli 2 = 30 (сверено по задачам; в шапке указано 30).

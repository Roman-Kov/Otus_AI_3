# Дизайн: итерация 2 — каталог книг на SQLite

Дата: 2026-10-04
Статус: утверждён пользователем
Предыдущая итерация: 2026-10-04-langchain-api-agent-design.md (домен пользователей)

## 1. Цель и решения

Заменить домен «пользователи» на **каталог книг** и перевести хранение из
in-memory в **SQLite**. Утверждённые решения:

| Вопрос | Решение |
|---|---|
| Судьба users-домена | Полностью заменить (API, tools, тесты, доки) |
| Хранение | SQLite через stdlib `sqlite3`, файл из настроек |
| Поля книги | Только `title` (+ служебные `id`, `created_at`) |
| Дубликаты названий | Запрещены: `UNIQUE`, при добавлении дубликата — 409 |
| Адресация | По названию (как имена пользователей в итерации 1) |

Операции (по запросу пользователя: добавлять, редактировать, удалять + список/статистика из задания):
**add / get-by-title / rename / delete / list / stats** — 6 операций.

## 2. Что меняется, что остаётся

**Остаётся:** архитектура (CLI → агент → tools → httpx → FastAPI), контракт
ответа `Status/Action/Data/Errors`, JSON-конверт tools
`{status, http_status, data, errors}`, debug-лог `tool result`, `[raw]`-fallback,
стек (LangGraph create_react_agent + Ollama qwen2.5:3b), src-layout, uv.

**Не меняются файлы:** `agent.py` (структура), `cli.py`, `main.py`, `pyproject.toml`.

**Меняются:** `store.py` (SQLite), `app.py` (роуты /books), `api_tools.py`
(6 tools), `prompts.py` (роль оператора каталога, удаление теперь валидно),
`config.py` (+`AGENT_DB_PATH`), тесты, README, report.md, docs/prompts.md,
`.env.example`, `.gitignore` (+`books.db`, `+.test-books.db`).

## 3. Модель и хранение

Книга: `{id: int, title: str, created_at: str(ISO UTC)}`.

Схема:

```sql
CREATE TABLE IF NOT EXISTS books (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    title TEXT NOT NULL UNIQUE,
    created_at TEXT NOT NULL
);
```

`BookStore(db_path: str = "")` — пустой путь означает «читать из
`get_settings().db_path` при каждой операции». Подключение открывается на каждую
операцию (`with sqlite3.connect(...) as conn`) — потокобезопасность по
построению, без общих состояний. Валидация названия (непустое, без `/`) — на
уровне API (pydantic), как в итерации 1.

Ошибки хранилища — исключения в `store.py`:

```python
class NotFoundError(Exception): ...
class ConflictError(Exception): ...
```

Методы: `add(title) -> dict` (ConflictError при дубликате);
`find_by_title(title) -> dict | None`; `rename(title, new_title) -> dict`
(NotFoundError | ConflictError если новое название занято);
`delete(title)` (NotFoundError); `all() -> list[dict]`;
`stats() -> {"total": int}`; `reset()` (очистка таблицы + сброс AUTOINCREMENT,
для тестов).

## 4. Контракт API (порт 8001)

| Метод | Endpoint | Успех | Ошибки |
|---|---|---|---|
| POST | `/books` `{title}` | 201, книга | 409 название занято; 422 пустое/с `/` |
| GET | `/books/{title}` | 200, книга | 404 |
| PATCH | `/books/{title}` `{new_title}` | 200, переименованная книга | 404; 409 новое название занято; 422 пустое/с `/` |
| DELETE | `/books/{title}` | 204, пустое тело | 404 |
| GET | `/books` | 200, список | — |
| GET | `/stats` | 200, `{"total": N}` | — |

Порядок проверок: PATCH — валидация pydantic → существование книги → конфликт
нового названия; DELETE — валидация pydantic → существование книги.
Название в пути URL-кодируется клиентом (`quote(name, safe='')` в tools).

## 5. Tools (src/api_agent/tools/api_tools.py)

Шесть, конверт и debug-лог без изменений:

- `add_book(title) -> str` — POST /books
- `get_book_by_title(title) -> str` — GET /books/{title}
- `rename_book(title, new_title) -> str` — PATCH /books/{title}
- `delete_book(title) -> str` — DELETE /books/{title} (204 → data: null)
- `list_books() -> str` — GET /books
- `get_catalog_stats() -> str` — GET /stats

`API_TOOLS` — список всех шести.

## 6. Промпт

Роль: «оператор каталога книг». Изменения против итерации 1:
- возможности: добавить/найти/переименовать/удалить книгу, список, статистика;
- удаление — поддерживаемая операция (пример отказа больше не «удаление»);
- отказ-кейс: неподдерживаемые действия (например, «выдай книгу на руки»);
- прочие правила, формат, 3 примера (успех / ошибка / «сколько») и НАПОМИНАНИЕ
  сохраняются из финальной версии итерации 1.

## 7. Конфигурация

`.env.example` (+новая строка, дефолт в `config.py`):

```
AGENT_DB_PATH=books.db
```

`.gitignore`: `books.db`, `.test-books.db` (тестовая БД conftest).

## 8. Тестирование

- `tests/test_store.py` — BookStore на `tmp_path`: add/конфликт, find,
  rename (успех/нет/конфликт), delete (успех/нет), all, stats, reset;
- `tests/test_api.py` — TestClient: 201/409/422 (POST), 200/404 (GET),
  200/404/409/422 (PATCH), 204/404 (DELETE), список, stats. Изоляция: conftest
  выставляет `AGENT_DB_PATH=<репо>/.test-books.db` ДО импорта `app` и делает
  autouse `store.reset()`;
- `tests/test_tools.py` — 6+ тестов против живого uvicorn: add success(201),
  add duplicate (409), get 404, rename success, delete success (204/null data),
  stats, кириллическое название roundtrip, спецсимволы (`?`, пробел),
  connection error;
- `test_config.py` — +`AGENT_DB_PATH` override; `test_agent.py`, `test_cli.py` — без изменений.

## 9. Проверочные запросы (для report.md)

1. «Добавь книгу Мастер и Маргарита» → `add_book` → POST /books → success
2. «Найди книгу Мастер и Маргарита» → `get_book_by_title` → GET /books/… → success
3. «Переименуй книгу Мастер и Маргарита в Мастер и Маргарита (булгаков)» → `rename_book` → PATCH → success
4. «Удали книгу Мастер и Маргарита (булгаков)» → `delete_book` → DELETE → success
5. «Сколько всего книг в каталоге?» → `get_catalog_stats` → GET /stats → success
6. Негативный: «Выдай книгу Война и мир читателю Ивану» → отказ (Status: error,
   без вызова tool)

## 10. Критерии задания — перенос

Все 7 критериев итерации 1 сохраняются, обновляются артефакты: README (запуск,
операции, контракт, карта кода), report.md (6 запросов + новая карта строк),
docs/prompts.md (синхрон с prompts.py). Секретов по-прежнему нет.

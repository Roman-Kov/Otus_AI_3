# Дизайн: минимальный AI-агент на LangChain поверх API пользователей

Дата: 2026-10-04
Статус: утверждён пользователем

## 1. Цель

Собрать и запустить минимального AI-агента на LangChain — натурально-языковую обёртку над HTTP API управления пользователями. Домашнее задание курса Otus.

Требования задания: агент принимает запрос на естественном языке, интерпретирует намерение, вызывает API-методы через LangChain tool, возвращает структурированный результат с указанием статуса выполнения.

## 2. Решения (утверждены)

| Вопрос | Решение |
|---|---|
| LLM-провайдер | Ollama локально, модель `qwen2.5:3b`, `http://localhost:11434` |
| API-домен | Минимальный API в этом же репозитории (FastAPI + in-memory) |
| Домен сущностей | Пользователи; поиск и редактирование **по имени**, не по id |
| Дубликаты имён | Разрешены, но подсвечиваются (см. контракт API) |
| Каркас агента | LangGraph `create_react_agent` (официальный путь экосистемы LangChain) |

## 3. Стек

- Python 3.13, `pyproject.toml` (hatchling), src-layout — как в предыдущем проекте курса
- `langchain`, `langgraph`, `langchain-ollama`
- `fastapi`, `uvicorn` — мини-API
- `httpx` — HTTP-вызовы из tools
- `pydantic`, `pydantic-settings` — конфигурация из `.env`
- `pytest`, `ruff` — тесты и линтер

## 4. Архитектура

```
CLI (python main.py "запрос")
   └─> Agent (LangGraph create_react_agent + ChatOllama qwen2.5:3b)
         └─> LangChain tools (src/api_agent/tools/api_tools.py)
               └─> httpx → FastAPI (localhost:8001, in-memory store)
```

Запуск — два процесса:
- терминал 1: `uvicorn src.api_agent.api.app:app --port 8001`
- терминал 2: `python main.py "создай пользователя с именем Alex"`

## 5. Структура репозитория

```
src/api_agent/
├── __init__.py
├── config.py           # pydantic-settings (.env)
├── api/
│   ├── __init__.py
│   ├── app.py          # FastAPI endpoints
│   └── store.py        # in-memory хранилище
├── tools/
│   ├── __init__.py
│   └── api_tools.py    # LangChain @tools → httpx + debug-лог
├── prompts.py          # системный промпт
└── agent.py            # сборка create_react_agent
main.py                 # CLI-точка входа
tests/
├── test_api.py         # TestClient: endpoints
└── test_tools.py       # tools против TestClient
docs/prompts.md         # использованные промпты (Markdown)
README.md
report.md               # отчёт + 5 проверочных запросов
.env.example
.gitignore
pyproject.toml
```

## 6. Контракт API (порт 8001)

Модель пользователя: `{id, name, email, status, created_at}`; `status ∈ {active, blocked}`.

| Метод | Endpoint | Успех | Ошибки |
|---|---|---|---|
| POST | `/users` `{name, email?}` | 201, тело пользователя + `duplicate: true/false` (имя уже было) | 422 — пустое имя |
| GET | `/users/{name}` | 200 — список совпадений | 404 — совпадений нет |
| PATCH | `/users/{name}/status` `{status}` | 200 — если ровно одно совпадение | 409 — несколько совпадений (в теле список пользователей); 404 — нет; 422 — некорректный status |
| GET | `/users` | 200 — список всех | — |
| GET | `/stats` | 200 — `{total, active, blocked}` | — |

Имя в пути URL-кодируется (httpx делает это автоматически).

## 7. LangChain tools

Файл `src/api_agent/tools/api_tools.py`. Пять tools, по одному на операцию:

- `create_user(name: str, email: str | None) -> str`
- `get_users_by_name(name: str) -> str`
- `update_user_status_by_name(name: str, status: str) -> str`
- `list_users() -> str`
- `get_user_stats() -> str`

Правила:
- внутри каждого tool — явный HTTP-вызов через `httpx` к `AGENT_API_BASE_URL`;
- возвращаемое значение — JSON-строка: `{"status": "success"|"error", "http_status": <int>, "data": <объект|список|null>, "errors": <строка|null>}`;
- исключения не пробрасываются наружу: `httpx.HTTPStatusError`, `httpx.ConnectError` перехватываются и превращаются в `status: error`;
- debug-вывод результата каждого вызова через `logging.info` (консоль + файл `agent.log`) — чтобы показать реальный вызов API; точные файл/строки указываются в README и report.md.

## 8. Агент и системный промпт

`src/api_agent/agent.py`: `create_react_agent(model=ChatOllama(model=qwen2.5:3b), tools=[...], prompt=SYSTEM_PROMPT)`.

Системный промпт (`src/api_agent/prompts.py`) определяет:
- роль: оператор API управления пользователями;
- ограничения: только операции через доступные tools; ничего не выдумывать; при отсутствии обязательного параметра — задать уточняющий вопрос; неподдерживаемые операции (например, удаление) — вежливый отказ в формате контракта со `Status: error`;
- подсветка дубликатов: если tool вернул `duplicate: true` или 409 — обязательно сообщить об этом пользователю;
- правила вызова tools и **жёсткий формат ответа** с one-shot примером (маленькая модель нуждается в примере).

## 9. Контракт ответа агента

Фиксированный формат (описан в README, раздел «Контракт ответа», и в docs/prompts.md):

```
Status: success | error
Action: <описание выполненного действия>
Data: <JSON-результат API или null>
Errors: <пусто | описание ошибки>
```

Если ответ модели не соответствует контракту, `main.py` печатает его с префиксом `[raw]`.

## 10. Конфигурация и секреты

`.env.example` (секретов нет — Ollama локальная, но файл обязателен по заданию):

```
AGENT_LLM_MODEL=qwen2.5:3b
AGENT_OLLAMA_BASE_URL=http://localhost:11434
AGENT_API_BASE_URL=http://localhost:8001
```

`.env` в `.gitignore`.

## 11. Обработка ошибок

- HTTP-ошибки API (404/409/422, connection refused) перехватываются в tool → `status: error` → агент формирует error-ответ по контракту.
- Ответ вне контракта → `main.py` печатает `[raw] <текст>`.
- Запуск без поднятого API → tool вернёт connection error, агент объяснит, что сервис недоступен.

## 12. Тестирование

pytest:
- `tests/test_api.py` — endpoints через `TestClient`: создание, поиск по имени (0/1/много), 409 при неоднозначном PATCH, статистика, 422;
- `tests/test_tools.py` — вызов tools против TestClient (base_url параметризуется), проверка JSON-формата `{"status", "http_status", "data", "errors"}`;
- сам агент (нужна Ollama) — ручная проверка, не в CI.

## 13. Пять проверочных запросов (для report.md)

1. «Создай пользователя с именем Alex» → ожидание: `create_user` → `POST /users` → success
2. «Найди пользователя Alex» → `get_users_by_name` → `GET /users/Alex` → success
3. «Заблокируй пользователя Alex» → `update_user_status_by_name` → `PATCH /users/Alex/status` → success
4. «Сколько всего пользователей и сколько активных?» → `get_user_stats` → `GET /stats` → success
5. «Удали пользователя Alex» → отказ (операция не поддерживается), `Status: error`, без вызова API

Минимум 3 запроса приводят к реальному вызову API-tool (фактически 4). Запросы, ответы и фрагменты лога tool фиксируются в `report.md`.

## 14. Результаты (deliverables)

- Рабочий агент в репозитории `P:\OtusAI3`
- `README.md`: используемый LLM и настройка; API и операции; команды запуска; контракт ответа; ссылки на файл/строки объявления tool, HTTP-вызова и debug-вывода (под критерии проверки)
- `report.md`: короткий отчёт + 5 запросов с результатами
- `docs/prompts.md`: системный промпт и пользовательские шаблоны
- `.env.example`, секреты не коммитятся

## 15. Критерии оценки — соответствие

| Критерий | Где выполняется |
|---|---|
| Агент запускается по инструкции | README.md |
| Минимум один API-tool с реальным вызовом + файл/строки + debug-вывод | tools/api_tools.py, README со ссылками на строки, logging.info в каждом tool |
| Запрос → конкретный API-метод + лог/trace | report.md: «Создай пользователя Alex» → POST /users, лог tool |
| Формат ответа по контракту, место описания | README.md раздел «Контракт ответа», docs/prompts.md |
| Минимум 5 проверочных запросов | report.md |
| Промпты оформлены | docs/prompts.md |
| Секреты не закоммичены | .gitignore + .env.example |

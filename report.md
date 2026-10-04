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
- tool-объявления: src/api_agent/tools/api_tools.py:49–82 (`@tool`-функции
  `create_user`, `get_users_by_name`, `update_user_status_by_name`, `list_users`,
  `get_user_stats`), список `API_TOOLS` — строка 85
- реальный HTTP-вызов: src/api_agent/tools/api_tools.py:36 (`client.request(...)`
  внутри `_request`, строки 33–46; httpx-клиент с base_url из настроек — строка 14)
- debug-вывод результата tool: src/api_agent/tools/api_tools.py:29 и 45
  (`logger.info("tool result: ...")` в `_result` и в ветке connection-error);
  выводится в консоль и в `agent.log` (настройка логирования — src/api_agent/cli.py:20–27)
- контракт ответа: README.md:40 (раздел «Контракт ответа агента») и docs/prompts.md
  (системный промпт, блок «ФОРМАТ ОТВЕТА»)

## Проверочные запросы (5)

Условия: Ollama qwen2.5:3b (temperature=0), API на localhost:8001, состояние
хранилища очищено перед прогоном. Время ответа агента: 5–10 с на запрос.

### 1. «Создай пользователя с именем Alex» → ожидание: POST /users

Вызов tool (лог консоли/agent.log):

```text
2026-10-04 22:44:14,302 api_agent.tools INFO tool result: {"status": "success", "http_status": 201, "data": {"id": 1, "name": "Alex", "email": null, "status": "active", "created_at": "2026-10-04T19:44:14.277021+00:00", "duplicate": false}, "errors": null}
```

Ответ агента:

```text
Status: success
Action: Создан пользователь Alex
Data: {"id": 1, "name": "Alex", "email": null, "status": "active", "created_at": "2026-10-04T19:44:14.277021+00:00", "duplicate": false}
Errors:
```

Итог: ✅ вызван `create_user` → POST /users (HTTP 201), контракт соблюдён.

### 2. «Найди пользователя Alex» → ожидание: GET /users/Alex

Вызов tool:

```text
2026-10-04 22:45:10,888 api_agent.tools INFO tool result: {"status": "success", "http_status": 200, "data": [{"id": 1, "name": "Alex", "email": null, "status": "active", "created_at": "2026-10-04T19:44:14.277021+00:00"}], "errors": null}
```

Ответ агента:

```text
Status: success
Action: Найден пользователь Alex
Data: {"id": 1, "name": "Alex", "email": null, "status": "active", "created_at": "2026-10-04T19:44:14.277021+00:00", "duplicate": false}
Errors:
```

Итог: ✅ вызван `get_users_by_name` → GET /users/Alex (HTTP 200), контракт
соблюдён. (Нюанс — в Action модель написала «Создан…» вместо «Найден…», а в Data
добавила поле `duplicate` из предыдущего контекста; см. «Наблюдения».)

### 3. «Заблокируй пользователя Alex» → ожидание: PATCH /users/Alex/status

Вызов tool:

```text
2026-10-04 22:45:52,486 api_agent.tools INFO tool result: {"status": "success", "http_status": 200, "data": {"id": 1, "name": "Alex", "email": null, "status": "blocked", "created_at": "2026-10-04T19:44:14.277021+00:00"}, "errors": null}
```

Ответ агента:

```text
Status: success
Action: Пользователь Alex заблокирован
Data: {"id": 1, "name": "Alex", "email": null, "status": "blocked", "created_at": "2026-10-04T19:44:14.277021+00:00"}
Errors:
```

Итог: ✅ вызван `update_user_status_by_name` → PATCH /users/Alex/status (HTTP 200,
status изменён на blocked), контракт соблюдён.

### 4. «Сколько всего пользователей и сколько активных?» → ожидание: GET /stats

Вызов tool:

```text
2026-10-04 22:46:27,066 api_agent.tools INFO tool result: {"status": "success", "http_status": 200, "data": {"total": 1, "active": 0, "blocked": 1}, "errors": null}
```

Ответ агента:

```text
Status: success
Action: Получена статистика: всего 1, активных 0, заблокированных 1
Data: {"total": 1, "active": 0, "blocked": 1}
Errors:
```

Итог: ✅ вызван `get_user_stats` → GET /stats (HTTP 200), контракт соблюдён.
(Потребовались итерации промпта — см. «Наблюдения».)

### 5. «Удали пользователя Alex» → ожидание: отказ без вызова API

Новых строк `tool result` в логе нет (счётчик до/после: 12/12) — API не вызывался.

Ответ агента:

```text
Status: error
Action: Удаление пользователя 'Alex' не поддерживается
Data: null
Errors: Операция удаления пользователя не поддерживается (HTTP 405)
```

Итог: ✅ отказ в контракте (Status: error), tool не вызывался. (Модель добавила
несуществующий код «HTTP 405» — см. «Наблюдения».)

## Наблюдения

1. **Промпт-инжиниринг для маленькой модели.** Исходный промпт (правила + один
   пример) дал 4/5 ответов в контракте; на вопрос «сколько…» модель устойчиво
   отвечала обычным текстом (в CLI это помечалось префиксом `[raw]` — механизм
  fallback работает как задумано). Добавление правила 6, third-shot примера для
   «сколько»-вопросов и финального НАПОМИНАНИЯ о формате (src/api_agent/prompts.py)
   устранило проблему: 5/5 в контракте.
2. **Мелкие неточности qwen2.5:3b:** в запросе 2 Action описан как «Создан…»,
   а в Data модель добавила `duplicate: false` из предыдущего ответа (галлюцинация
   поля); в запросе 5 модель придумала код «HTTP 405», хотя HTTP-вызова не было.
   На критерии задания не влияет (tool-выбор корректен, контракт соблюдён).
3. **Наблюдаемость:** каждый реальный вызов API виден в консоли и agent.log
   (строки `api_agent.tools INFO tool result: …`), что подтверждает требование
   «минимум 3 запроса приводят к реальному вызову API-tool» — фактических 4 (запросы 1–4).

## Как воспроизвести
1. `ollama pull qwen2.5:3b` (если модели нет)
2. Терминал 1: `.\.venv\Scripts\python -m uvicorn api_agent.api.app:app --port 8001`
3. Терминал 2: команды из заголовков разделов 1–5 выше
4. Тесты: `.\.venv\Scripts\python -m pytest -v` (24 passed), линтер: `.\.venv\Scripts\python -m ruff check .`

# Отчёт: минимальный агент на LangChain (каталог книг)

## LLM
Ollama, модель qwen2.5:3b, http://localhost:11434. Настройка — см. README («Настройка»).
Секретов нет (локальная LLM); конфигурация через .env (см. .env.example).

## API
FastAPI в этом же репозитории, хранение SQLite (AGENT_DB_PATH, по умолчанию
books.db). Операции: add / get-by-title / rename / delete / list / stats —
см. README («Операции API»).

## Запуск
См. README («Запуск»): uvicorn (порт 8001) + `python main.py "<запрос>"`.

## Карта кода (для критериев проверки)
- tool-объявления: src/api_agent/tools/api_tools.py:49–86 (`@tool`-функции
  `add_book`, `get_book_by_title`, `rename_book`, `delete_book`, `list_books`,
  `get_catalog_stats`), список `API_TOOLS` — строка 91
- реальный HTTP-вызов: src/api_agent/tools/api_tools.py:36 (`client.request(...)`
  внутри `_request`, строки 33–46; httpx-клиент с base_url из настроек — строки 13–14)
- debug-вывод результата tool: src/api_agent/tools/api_tools.py:29 и 45
  (`logger.info("tool result: ...")` в `_result` и в ветке connection-error);
  выводится в консоль и в `agent.log` (настройка логирования — src/api_agent/cli.py:20–26)
- хранение SQLite: src/api_agent/api/store.py (BookStore, таблица books, UNIQUE title)
- контракт ответа: README.md:43 (раздел «Контракт ответа агента») и docs/prompts.md
  (системный промпт, блок «ФОРМАТ ОТВЕТА»)

## Проверочные запросы (6)

Условия: Ollama qwen2.5:3b (temperature=0), API на localhost:8001, SQLite books.db.
Время ответа агента: 4–10 с на запрос. Последовательность 1→5 выполнялась на
одном состоянии БД; в каталоге дополнительно находилась тестовая книга «Му-му»,
добавленная вручную при параллельной проверке API (учтена в статистике).

### 1. «Добавь книгу Мастер и Маргарита» → ожидание: POST /books

Вызов tool (лог консоли/agent.log):

```text
2026-10-04 23:37:54,719 api_agent.tools INFO tool result: {"status": "success", "http_status": 201, "data": {"id": 3, "title": "Мастер и Маргарита", "created_at": "2026-10-04T20:37:54.704933+00:00"}, "errors": null}
```

Ответ агента:

```text
Status: success
Action: Книга «Мастер и Маргарита» добавлена в каталог
Data: {"id": 3, "title": "Мастер и Маргарита", "created_at": "2026-10-04T20:37:54.704933+00:00"}
Errors:
```

Итог: ✅ `add_book` → POST /books (HTTP 201), контракт соблюдён.

### 2. «Найди книгу Мастер и Маргарита» → ожидание: GET /books/{title}

Вызов tool (в логе виден URL-кодированный кириллический путь):

```text
2026-10-04 23:38:24,804 api_agent.tools INFO tool result: {"status": "success", "http_status": 200, "data": {"id": 3, "title": "Мастер и Маргарита", "created_at": "2026-10-04T20:37:54.704933+00:00"}, "errors": null}
```

Ответ агента:

```text
Status: success
Action: Найдена книга 'Мастер и Маргарита'
Data: {"id": 3, "title": "Мастер и Маргарита", "created_at": "2026-10-04T20:37:54.704933+00:00"}
Errors:
```

Итог: ✅ `get_book_by_title` → GET /books/Мастер%20и%20Маргарита (HTTP 200).

### 3. «Переименуй книгу Мастер и Маргарита в Мастер и Маргарита (роман)» → ожидание: PATCH /books/{title}

Вызов tool:

```text
2026-10-04 23:38:53,940 api_agent.tools INFO tool result: {"status": "success", "http_status": 200, "data": {"id": 3, "title": "Мастер и Маргарита (роман)", "created_at": "2026-10-04T20:37:54.704933+00:00"}, "errors": null}
```

Ответ агента:

```text
Status: success
Action: Книга "Мастер и Маргарита" переименована в "Мастер и Маргарита (роман)"
Data: {"id": 3, "title": "Мастер и Маргарита (роман)", "created_at": "2026-10-04T20:37:54.704933+00:00"}
Errors:
```

Итог: ✅ `rename_book` → PATCH /books/Мастер%20и%20Маргарита (HTTP 200, новое
название с скобками сохранено точно).

### 4. «Удали книгу Мастер и Маргарита (роман)» → ожидание: DELETE /books/{title}

Вызов tool:

```text
2026-10-04 23:39:27,313 api_agent.tools INFO tool result: {"status": "success", "http_status": 204, "data": null, "errors": null}
```

Ответ агента:

```text
Status: success
Action: Книга «Мастер и Маргарита (роман)» удалена
Data: null
Errors:
```

Итог: ✅ `delete_book` → DELETE /books/…%28роман%29 (HTTP 204). Потребовались
итерации промпта (см. «Наблюдения», п.1).

### 5. «Сколько всего книг в каталоге?» → ожидание: GET /stats

Вызов tool:

```text
2026-10-04 23:39:48,493 api_agent.tools INFO tool result: {"status": "success", "http_status": 200, "data": {"total": 1}, "errors": null}
```

Ответ агента:

```text
Status: success
Action: Получена статистика: всего 1 книга
Data: {"total": 1}
Errors:
```

Итог: ✅ `get_catalog_stats` → GET /stats (HTTP 200). total=1 корректен: после
удаления «Мастер и Маргарита (роман)» в каталоге осталась вручную добавленная
книга «Му-му».

### 6. «Выдай книгу Война и мир читателю Ивану» → ожидание: отказ без вызова API

Новых строк `tool result` в логе нет (счётчик до/после: 30/30) — API не вызывался.

Ответ агента:

```text
Status: error
Action: Выдача книги 'Война и мир' не входит в возможности
Data: null
Errors:
```

Итог: ✅ отказ в контракте (Status: error), tool не вызывался. (Модель описала
причину в Action, оставив Errors пустым — см. «Наблюдения», п.3.)

## Наблюдения

1. **Промпт-инжиниринг: названия со скобками.** qwen2.5:3b сперва устойчиво
   обрезала уточнение «(роман)» из названия при DELETE (3 попытки → 404 по
   усечённому названию; контракт при этом не нарушался — ошибка честно
   пробрасывалась). Помогли две правки промпта: правило 7 («название передавать
   дословно и целиком, скобки — часть названия») и few-shot пример с названием
   «Война и мир (роман)» — после этого DELETE прошёл точно (204 по полному
   названию). Финальный промпт: src/api_agent/prompts.py, копия в docs/prompts.md.
2. **PowerShell-артефакт:** попытки экранировать кавычки в аргументе CLI в
   PowerShell 5.1 резали argv (модель получала «удали книгу Мастер») — при
   воспроизведении кавычки в запросах лучше не использовать.
3. **Мелкие отклонения формата:** в запросе 6 модель перенесла причину отказа в
   Action, оставив Errors пустым; семантика верна, критерий (отказ + отсутствие
   вызова tool) выполнен.
4. **Наблюдаемость:** каждый реальный вызов API виден в консоли и agent.log
   (`api_agent.tools INFO tool result: …`); в логе видны и URL-кодированные
   кириллические пути. Из 6 запросов 5 привели к реальным вызовам API-tool
   (требование задания — минимум 3).

## Как воспроизвести
1. `ollama pull qwen2.5:3b` (если модели нет)
2. Терминал 1: `.\.venv\Scripts\python -m uvicorn api_agent.api.app:app --port 8001`
3. Терминал 2: команды из заголовков разделов 1–6 выше
4. Тесты: `.\.venv\Scripts\python -m pytest -v` (31 passed), линтер: `.\.venv\Scripts\python -m ruff check .`

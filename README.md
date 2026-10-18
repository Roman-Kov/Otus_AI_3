# Каталог книг: AI-агент на LangChain (OtusAI3)

Минимальный AI-агент — натурально-языковая обёртка над HTTP API каталога книг
(добавление, поиск, переименование, удаление, список, статистика). Задание курса
Otus «Минимальный агент на LangChain».

## Стек
- LLM: Ollama, модель `qwen2.5:3b` (локально, ключи не нужны)
- Агент: LangChain + LangGraph `create_react_agent`
- API: FastAPI (в этом же репозитории)
- Хранение: SQLite (файл из `AGENT_DB_PATH`, по умолчанию `books.db`)

## Docker (одна команда)
Нужен только Docker (на Windows — Docker Desktop). Python и Ollama на хосте не требуются.

```powershell
docker compose up --build -d
```

Поднимает API (`:8001`), Ollama с моделью `qwen2.5:3b` (первый запуск скачивает
~2 ГБ) и volumes для модели и БД. Запрос агенту:

```powershell
docker compose run --rm agent "добавь книгу Мастер и Маргарита"
```

Остановка — `docker compose down` (модель и БД сохранятся в volumes).
Модель можно переопределить: `$env:AGENT_LLM_MODEL="qwen2.5:1.5b"; docker compose up -d --build`.

## Настройка
1. Python 3.11+
2. Установить [Ollama](https://ollama.com), затем:
   `ollama pull qwen2.5:3b`
3. Окружение:
   - uv: `uv venv; uv sync`
   - или: `python -m venv .venv; .\.venv\Scripts\pip install -e .; .\.venv\Scripts\pip install pytest ruff`
4. `Copy-Item .env.example .env` (при необходимости поправьте: модель, URL, путь к БД)

## Запуск (два терминала)
Терминал 1 — API:
```powershell
.\.venv\Scripts\python -m uvicorn api_agent.api.app:app --port 8001
```

Терминал 2 — агент:
```powershell
.\.venv\Scripts\python main.py "добавь книгу Мастер и Маргарита"
```

## Операции API
| Метод | Endpoint | Описание |
|---|---|---|
| POST | `/books` `{title}` | добавить; 409 если название занято; `/` в названии запрещён (422) |
| GET | `/books/{title}` | книга; 404 если нет |
| PATCH | `/books/{title}` `{new_title}` | переименовать; 404 если нет; 409 если новое название занято; 422 невалидно |
| DELETE | `/books/{title}` | удалить; 204; 404 если нет |
| GET | `/books` | все книги |
| GET | `/stats` | `{"total": N}` |

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
  (tools `add_book`, `get_book_by_title`, `rename_book`, `delete_book`,
  `list_books`, `get_catalog_stats`; HTTP — `client.request(...)` внутри `_request`).
  Точные диапазоны строк см. в `report.md` (раздел «Карта кода»).
- Debug-вывод результата tool: `logger.info("tool result: ...")` в
  `src/api_agent/tools/api_tools.py` (функции `_result` и `_request`) —
  выводится в консоль и в `agent.log`.
- Хранение: `src/api_agent/api/store.py` — BookStore на SQLite (таблица books,
  UNIQUE title).
- Системный промпт: `src/api_agent/prompts.py`, копия — `docs/prompts.md`.

## Тесты
```powershell
.\.venv\Scripts\python -m pytest -v
```

## Отчёт
Результаты проверки — `report.md`. Использованные промпты — `docs/prompts.md`.

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

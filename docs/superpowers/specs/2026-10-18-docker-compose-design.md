# Docker Compose: развёртывание проекта одной командой (подход A)

Дата: 2026-10-18
Статус: утверждён (дизайн одобрен пользователем)

## Контекст

Замечание проверяющего курса: подключить Docker, чтобы проект разворачивался
в контейнерах и запуск на любой машине осуществлялся одной командой
`docker compose up --build`.

Сейчас для запуска нужны: Python 3.11+, установленные Ollama + модель
`qwen2.5:3b`, venv, два терминала (API и агент).

## Решение

- Ollama живёт **внутри compose** (полная автономность на любой машине с Docker).
- Форма агента — **подход A**: обычный `up` разворачивает сервисы, агент
  выполняется по запросу через `docker compose run --rm agent "..."`.
  REPL/веб-чат не добавляем (пользователь выбрал минимум изменений).
- Ноль правок существующего кода: только новые файлы и раздел в README.

## Новые файлы

### `Dockerfile`

Один образ для `api` и `agent`:

- база `python:3.11-slim`;
- копируются `pyproject.toml`, `src/`, `main.py`;
- `pip install .` (зависимости чистые, компилятор не нужен);
- CMD по умолчанию: `uvicorn api_agent.api.app:app --host 0.0.0.0 --port 8001`.

### `.dockerignore`

`.git`, `.venv`, `*.db`, `*.log`, `.env`, кэши (`.pytest_cache`, `.ruff_cache`,
`__pycache__`), `docs/`, `tests/`, `report.md` — в образ не попадают.

### `docker-compose.yml`

| Сервис | Образ | Назначение | Ключевое |
|---|---|---|---|
| `ollama` | `ollama/ollama` | LLM-движок | модели в named volume `ollama_models`; порт наружу не публикуется; healthcheck `ollama list` |
| `ollama-init` | `ollama/ollama` | one-shot | `OLLAMA_HOST=http://ollama:11434`, команда `ollama pull qwen2.5:3b`; depends_on: `ollama` healthy; при повторных запусках мгновенно выходит |
| `api` | сборка из `Dockerfile` | FastAPI | порты `8001:8001`; `AGENT_DB_PATH=/data/books.db`, БД в named volume `books_data`; healthcheck `GET /stats` через python/httpx; от Ollama не зависит |
| `agent` | тот же образ | CLI-агент | profile `agent` (не стартует при обычном `up`); env `AGENT_OLLAMA_BASE_URL=http://ollama:11434`, `AGENT_API_BASE_URL=http://api:8001`, `AGENT_LLM_MODEL=qwen2.5:3b`; command `python main.py`; depends_on: `api` healthy + `ollama-init` completed_successfully |

Модель можно переопределить переменной `AGENT_LLM_MODEL` (по умолчанию
`qwen2.5:3b`): она параметризует и `ollama pull`, и env агента.

## Использование

```powershell
docker compose up --build -d                          # развернуть всё
docker compose run --rm agent "добавь книгу Мастер и Маргарита"
docker compose down                                    # остановить (volumes сохранятся)
```

У агента `entrypoint: ["python", "main.py"]`: аргументы `compose run` становятся
command и дописываются к entrypoint — агент получает запрос как `sys.argv[1]`,
как и при локальном запуске.

## README

Новый раздел «Docker (одна команда)» перед «Настройка»: команды выше, примечание
о первом запуске (скачивание модели ~2 ГБ) и о том, что Python/Ollama на хосте
не нужны.

## Обработка ошибок

- `ollama-init` падает → `docker compose up` явно сообщает об ошибке.
- Агент не стартует, пока API не прошёл healthcheck, а `ollama-init` не завершился
  успешно — гонок на старте нет.
- Повторный `up` после `down`: модель и БД берутся из volumes, ничего не качается
  заново.

## Критерии приёмки

1. `docker compose up --build -d` → `ollama` и `api` healthy, `ollama-init` completed.
2. `docker compose run --rm agent "добавь книгу Мастер и Маргарита"` → ответ
   в контракте (Status/Action/Data/Errors), книга в каталоге.
3. `GET http://localhost:8001/stats` → `{"total": N}` с учётом добавленной книги.
4. `docker compose down && docker compose up -d` → модель не качается заново,
   БД не теряется.

## Что не меняем

`main.py`, `src/**`, `pyproject.toml`, `.env.example` — без изменений.

## Риски

- Первый запуск скачивает ~2 ГБ модели — нормальная цена автономности
  (примечание в README).
- `ollama/ollama` на Windows-хостах требует WSL2/Docker Desktop — стандартное
  требование Docker на Windows.

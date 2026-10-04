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

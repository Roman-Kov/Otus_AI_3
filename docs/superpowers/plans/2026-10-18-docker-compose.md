# Docker Compose развёртывание — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Проект разворачивается в Docker одной командой `docker compose up --build`; запрос агенту — `docker compose run --rm agent "..."`.

**Architecture:** Один образ `python:3.11-slim` для API и агента. Compose поднимает `ollama` (модели в named volume), one-shot `ollama-init` (тянет модель), `api` (порт 8001, SQLite в volume) и `agent` под profile `agent`. Код проекта не меняется.

**Tech Stack:** Docker, Docker Compose v2, pip. Существующий стек (FastAPI, LangChain, Ollama) — без изменений.

**Спек:** `docs/superpowers/specs/2026-10-18-docker-compose-design.md`

**Особенность тестирования:** правок Python-кода нет, поэтому pytest не применяется. Проверка каждого шага — реальные docker-команды и их ожидаемый вывод (критерии приёмки из спека). Первые запуск/сборка долгие (модель ~2 ГБ) — ставить timeout команд от 10 минут.

---

### Task 1: `.dockerignore`

**Files:**
- Create: `P:\OtusAI3\.dockerignore`

- [ ] **Step 1: Создать `.dockerignore`**

```
.git
.venv
.env
*.db
*.log
.pytest_cache
.ruff_cache
**/__pycache__
docs/
tests/
report.md
Dockerfile
docker-compose.yml
```

- [ ] **Step 2: Проверить, что файл на месте**

Run: `Get-Content .dockerignore`
Expected: содержимое выше.

- [ ] **Step 3: Commit**

```powershell
git add .dockerignore
git commit -m "chore: .dockerignore — чистый контекст сборки"
```

---

### Task 2: `Dockerfile`

**Files:**
- Create: `P:\OtusAI3\Dockerfile`

- [ ] **Step 1: Создать `Dockerfile`**

```dockerfile
FROM python:3.11-slim

WORKDIR /app

COPY pyproject.toml ./
COPY src ./src
COPY main.py ./

RUN pip install --no-cache-dir .

EXPOSE 8001

CMD ["uvicorn", "api_agent.api.app:app", "--host", "0.0.0.0", "--port", "8001"]
```

- [ ] **Step 2: Собрать образ (включая скачивание python:3.11-slim и pip install)**

Run: `docker build -t otusai3 .` (timeout ≥ 10 мин)
Expected: `Successfully built` / `naming to docker.io/library/otusai3` без ошибок.

- [ ] **Step 3: Smoke-проверка образа**

Run: `docker run --rm otusai3 python -c "import api_agent, main; print('ok')"`
Expected: `ok`

- [ ] **Step 4: Commit**

```powershell
git add Dockerfile
git commit -m "feat: Dockerfile — образ для API и агента (python:3.11-slim)"
```

---

### Task 3: `docker-compose.yml`

**Files:**
- Create: `P:\OtusAI3\docker-compose.yml`

- [ ] **Step 1: Создать `docker-compose.yml`**

```yaml
services:
  ollama:
    image: ollama/ollama:latest
    volumes:
      - ollama_models:/root/.ollama
    healthcheck:
      test: ["CMD", "ollama", "list"]
      interval: 5s
      timeout: 5s
      retries: 12
      start_period: 10s

  ollama-init:
    image: ollama/ollama:latest
    depends_on:
      ollama:
        condition: service_healthy
    environment:
      OLLAMA_HOST: http://ollama:11434
    entrypoint: ["/bin/sh", "-c"]
    command: ["ollama pull ${AGENT_LLM_MODEL:-qwen2.5:3b}"]
    restart: "no"

  api:
    build: .
    environment:
      AGENT_DB_PATH: /data/books.db
    ports:
      - "8001:8001"
    volumes:
      - books_data:/data
    healthcheck:
      test: ["CMD", "python", "-c", "import httpx; httpx.get('http://localhost:8001/stats')"]
      interval: 5s
      timeout: 5s
      retries: 12
      start_period: 10s

  agent:
    build: .
    profiles: ["agent"]
    entrypoint: ["python", "main.py"]
    command: []
    environment:
      AGENT_LLM_MODEL: ${AGENT_LLM_MODEL:-qwen2.5:3b}
      AGENT_OLLAMA_BASE_URL: http://ollama:11434
      AGENT_API_BASE_URL: http://api:8001
    depends_on:
      api:
        condition: service_healthy
      ollama-init:
        condition: service_completed_successfully

volumes:
  ollama_models:
  books_data:
```

- [ ] **Step 2: Валидация файла**

Run: `docker compose config --quiet`
Expected: пустой вывод, код 0. Ошибки YAML/схемы — исправить до перехода дальше.

- [ ] **Step 3: Commit**

```powershell
git add docker-compose.yml
git commit -m "feat: docker-compose — ollama + api + agent одной командой"
```

---

### Task 4: Запуск и приёмочные проверки

**Files:** новых нет. Правки `docker-compose.yml` — только если проверки вскроют проблемы.

- [ ] **Step 1: Поднять всё (первый раз качает модель ~2 ГБ)**

Run: `docker compose up --build -d` (timeout ≥ 20 мин)
Expected: контейнеры созданы, ошибок нет.

- [ ] **Step 2: Дождаться healthy**

Run: `docker compose ps`
Expected: `ollama` — healthy; `api` — healthy; `ollama-init` — exited (0).
Если не так — `docker compose logs ollama-init` / `logs api`, разобраться.

- [ ] **Step 3: Проверить API**

Run: `Invoke-RestMethod http://localhost:8001/stats`
Expected: `total` — число (пустой каталог: 0).

- [ ] **Step 4: Запрос агенту**

Run: `docker compose run --rm agent "добавь книгу Мастер и Маргарита"` (timeout ≥ 10 мин)
Expected: ответ в контракте `Status: success`, `Action: ...`, `Data: {...}`.

- [ ] **Step 5: Проверить, что книга попала в каталог**

Run: `Invoke-RestMethod http://localhost:8001/stats`
Expected: `total` = значение из Step 3 + 1.

- [ ] **Step 6: Персистентность volumes**

Run: `docker compose down; docker compose up -d` (timeout ≥ 10 мин)
Expected: `docker compose logs ollama-init` показывает мгновенный `pull`
(«pulling manifest» без повторного скачивания слоёв);
`Invoke-RestMethod http://localhost:8001/stats` → книга из Step 4 на месте.

- [ ] **Step 7: Commit (если были правки compose)**

```powershell
git add docker-compose.yml
git commit -m "fix: правки compose по результатам приёмочных проверок"
```

(если правок не было — пропустить)

---

### Task 5: README — раздел «Docker»

**Files:**
- Modify: `P:\OtusAI3\README.md` (вставить раздел перед `## Настройка`)

- [ ] **Step 1: Добавить раздел**

```markdown
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
```

(внутренние тройные бэктики экранировать вложенностью блока — вставить как обычный markdown-фрагмент)

- [ ] **Step 2: Проверить рендер**

Run: `Select-String -Path README.md -Pattern "Docker"`
Expected: раздел на месте, перед `## Настройка`.

- [ ] **Step 3: Commit**

```powershell
git add README.md
git commit -m "docs: раздел Docker в README — запуск одной командой"
```

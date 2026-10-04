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

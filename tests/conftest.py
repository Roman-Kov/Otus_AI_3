import threading
import time

import httpx
import pytest
import uvicorn

from api_agent.config import get_settings

API_PORT = 8977
API_URL = f"http://127.0.0.1:{API_PORT}"


@pytest.fixture(autouse=True)
def reset_store():
    try:
        from api_agent.api.app import store
    except ImportError:
        # B2-лимбо: store.py уже книжный, app.py ещё users-домен (чинится в B3)
        store = None
    if store is not None:
        store.reset()
    yield


@pytest.fixture(autouse=True)
def clear_settings_cache():
    yield
    get_settings.cache_clear()


@pytest.fixture(scope="session")
def api_server():
    from api_agent.api.app import app

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

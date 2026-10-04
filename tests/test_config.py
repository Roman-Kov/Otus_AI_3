from api_agent.config import get_settings


def test_env_overrides_defaults(monkeypatch):
    monkeypatch.setenv("AGENT_API_BASE_URL", "http://example:1234")
    monkeypatch.setenv("AGENT_DB_PATH", "C:/tmp/x.db")
    get_settings.cache_clear()
    s = get_settings()
    assert s.api_base_url == "http://example:1234"
    assert s.db_path == "C:/tmp/x.db"
    assert s.llm_model == "qwen2.5:3b"
    assert s.ollama_base_url == "http://localhost:11434"
    get_settings.cache_clear()


def test_db_path_default():
    get_settings.cache_clear()
    s = get_settings()
    assert s.db_path == "books.db"
    get_settings.cache_clear()

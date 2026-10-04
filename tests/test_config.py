from api_agent.config import get_settings


def test_env_overrides_defaults(monkeypatch):
    monkeypatch.setenv("AGENT_API_BASE_URL", "http://example:1234")
    get_settings.cache_clear()
    s = get_settings()
    assert s.api_base_url == "http://example:1234"
    assert s.llm_model == "qwen2.5:3b"
    assert s.ollama_base_url == "http://localhost:11434"
    get_settings.cache_clear()

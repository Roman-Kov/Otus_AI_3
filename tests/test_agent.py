from api_agent.agent import build_agent


def test_build_agent_returns_invokable_graph():
    agent = build_agent()
    assert callable(agent.invoke)

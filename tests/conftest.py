import pytest

from api_agent.api.app import store


@pytest.fixture(autouse=True)
def reset_store():
    store.reset()
    yield

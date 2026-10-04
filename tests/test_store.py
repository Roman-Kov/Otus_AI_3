from api_agent.api.store import UserStore


def test_create_and_duplicate():
    s = UserStore()
    u, dup = s.create("Alex", None)
    assert u["name"] == "Alex"
    assert u["status"] == "active"
    assert u["id"] == 1
    assert dup is False
    _, dup2 = s.create("Alex", None)
    assert dup2 is True


def test_find_by_name():
    s = UserStore()
    s.create("Bob", None)
    s.create("Bob", None)
    assert len(s.find_by_name("Bob")) == 2
    assert s.find_by_name("Nope") == []


def test_update_status_single_and_ambiguous():
    s = UserStore()
    s.create("Carl", None)
    updated = s.update_status("Carl", "blocked")
    assert updated["status"] == "blocked"
    s.create("Carl", None)
    assert s.update_status("Carl", "active") is None


def test_stats():
    s = UserStore()
    s.create("A", None)
    s.create("B", None)
    s.update_status("B", "blocked")
    assert s.stats() == {"total": 2, "active": 1, "blocked": 1}


def test_reset():
    s = UserStore()
    s.create("X", None)
    s.reset()
    assert s.stats()["total"] == 0

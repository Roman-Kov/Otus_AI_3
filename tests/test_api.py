from fastapi.testclient import TestClient

from api_agent.api.app import app

client = TestClient(app)


def test_create_user_201_and_duplicate_flag():
    r1 = client.post("/users", json={"name": "Alex"})
    assert r1.status_code == 201
    body = r1.json()
    assert body["name"] == "Alex"
    assert body["status"] == "active"
    assert body["duplicate"] is False
    r2 = client.post("/users", json={"name": "Alex"})
    assert r2.status_code == 201
    assert r2.json()["duplicate"] is True


def test_create_user_empty_name_422():
    r = client.post("/users", json={"name": ""})
    assert r.status_code == 422


def test_create_user_slash_in_name_422():
    r = client.post("/users", json={"name": "a/b"})
    assert r.status_code == 422


def test_get_by_name_found_and_404():
    client.post("/users", json={"name": "Bob"})
    r = client.get("/users/Bob")
    assert r.status_code == 200
    assert [u["name"] for u in r.json()] == ["Bob"]
    assert client.get("/users/Nobody").status_code == 404


def test_patch_status_success_409_404():
    client.post("/users", json={"name": "Carl"})
    r = client.patch("/users/Carl/status", json={"status": "blocked"})
    assert r.status_code == 200
    assert r.json()["status"] == "blocked"

    client.post("/users", json={"name": "Carl"})
    r = client.patch("/users/Carl/status", json={"status": "active"})
    assert r.status_code == 409
    assert "users" in r.json()["detail"]

    assert client.patch("/users/Ghost/status", json={"status": "blocked"}).status_code == 404


def test_patch_invalid_status_422():
    client.post("/users", json={"name": "Dan"})
    r = client.patch("/users/Dan/status", json={"status": "deleted"})
    assert r.status_code == 422


def test_stats():
    client.post("/users", json={"name": "A"})
    client.post("/users", json={"name": "B"})
    client.patch("/users/B/status", json={"status": "blocked"})
    assert client.get("/stats").json() == {"total": 2, "active": 1, "blocked": 1}


def test_list_users():
    client.post("/users", json={"name": "Ann"})
    r = client.get("/users")
    assert [u["name"] for u in r.json()] == ["Ann"]

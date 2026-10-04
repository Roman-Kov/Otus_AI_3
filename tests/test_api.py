from fastapi.testclient import TestClient

from api_agent.api.app import app

client = TestClient(app)


def test_add_book_201():
    r = client.post("/books", json={"title": "Мастер и Маргарита"})
    assert r.status_code == 201
    body = r.json()
    assert body["title"] == "Мастер и Маргарита"
    assert body["id"] == 1
    assert body["created_at"]


def test_add_book_duplicate_409():
    client.post("/books", json={"title": "Война и мир"})
    r = client.post("/books", json={"title": "Война и мир"})
    assert r.status_code == 409


def test_add_book_invalid_422():
    assert client.post("/books", json={"title": ""}).status_code == 422
    assert client.post("/books", json={"title": "а/б"}).status_code == 422


def test_get_book_200_404():
    client.post("/books", json={"title": "Мы"})
    r = client.get("/books/Мы")
    assert r.status_code == 200
    assert r.json()["title"] == "Мы"
    assert client.get("/books/Призрак").status_code == 404


def test_rename_book_200_404_409():
    client.post("/books", json={"title": "Мы"})
    r = client.patch("/books/Мы", json={"new_title": "Мы (замятин)"})
    assert r.status_code == 200
    assert r.json()["title"] == "Мы (замятин)"

    assert client.patch("/books/Призрак", json={"new_title": "X"}).status_code == 404

    client.post("/books", json={"title": "Занято"})
    r = client.patch("/books/Мы (замятин)", json={"new_title": "Занято"})
    assert r.status_code == 409


def test_rename_invalid_422():
    client.post("/books", json={"title": "Мы"})
    assert client.patch("/books/Мы", json={"new_title": ""}).status_code == 422
    assert client.patch("/books/Мы", json={"new_title": "а/б"}).status_code == 422


def test_delete_book_204_404():
    client.post("/books", json={"title": "Мы"})
    r = client.delete("/books/Мы")
    assert r.status_code == 204
    assert r.content == b""
    assert client.get("/books/Мы").status_code == 404
    assert client.delete("/books/Мы").status_code == 404


def test_list_books_and_stats():
    client.post("/books", json={"title": "А"})
    client.post("/books", json={"title": "Б"})
    assert [b["title"] for b in client.get("/books").json()] == ["А", "Б"]
    client.delete("/books/А")
    assert client.get("/stats").json() == {"total": 1}

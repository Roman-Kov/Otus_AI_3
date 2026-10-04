import pytest

from api_agent.api.store import BookStore, ConflictError, NotFoundError


@pytest.fixture()
def s(tmp_path):
    return BookStore(str(tmp_path / "books.db"))


def test_add_and_find(s):
    book = s.add("Мастер и Маргарита")
    assert book["title"] == "Мастер и Маргарита"
    assert book["id"] == 1
    assert book["created_at"]
    assert s.find_by_title("Мастер и Маргарита") == book
    assert s.find_by_title("Нет такой") is None


def test_add_duplicate_raises_conflict(s):
    s.add("Война и мир")
    with pytest.raises(ConflictError):
        s.add("Война и мир")


def test_rename(s):
    s.add("Война и мир")
    renamed = s.rename("Война и мир", "Война и мир (сокращённая)")
    assert renamed["title"] == "Война и мир (сокращённая)"
    assert renamed["id"] == 1
    assert s.find_by_title("Война и мир") is None
    assert s.find_by_title("Война и мир (сокращённая)") is not None


def test_rename_not_found(s):
    with pytest.raises(NotFoundError):
        s.rename("Призрак", "Другое")


def test_rename_conflict(s):
    s.add("Книга А")
    s.add("Книга Б")
    with pytest.raises(ConflictError):
        s.rename("Книга А", "Книга Б")


def test_delete(s):
    s.add("Книга А")
    s.delete("Книга А")
    assert s.find_by_title("Книга А") is None
    assert s.stats() == {"total": 0}


def test_delete_not_found(s):
    with pytest.raises(NotFoundError):
        s.delete("Призрак")


def test_all_and_stats(s):
    s.add("Книга А")
    s.add("Книга Б")
    assert [b["title"] for b in s.all()] == ["Книга А", "Книга Б"]
    assert s.stats() == {"total": 2}


def test_reset_restarts_ids(s):
    s.add("Книга А")
    s.reset()
    assert s.stats() == {"total": 0}
    assert s.add("Книга Б")["id"] == 1


def test_persistence_across_instances(tmp_path):
    db = str(tmp_path / "books.db")
    BookStore(db).add("Пикник на обочине")
    second = BookStore(db)
    assert second.find_by_title("Пикник на обочине") is not None

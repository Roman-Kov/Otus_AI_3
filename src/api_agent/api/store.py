import sqlite3
from datetime import UTC, datetime

from ..config import get_settings


class NotFoundError(Exception):
    """Книга не найдена."""


class ConflictError(Exception):
    """Конфликт уникальности названия."""


_SCHEMA = """
CREATE TABLE IF NOT EXISTS books (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    title TEXT NOT NULL UNIQUE,
    created_at TEXT NOT NULL
)
"""


class BookStore:
    """Каталог книг в SQLite. Подключение открывается на каждую операцию."""

    def __init__(self, db_path: str = "") -> None:
        self._db_path = db_path
        self._init_schema()

    def _path(self) -> str:
        return self._db_path or get_settings().db_path

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self._path())
        conn.row_factory = sqlite3.Row
        return conn

    def _init_schema(self) -> None:
        with self._connect() as conn:
            conn.execute(_SCHEMA)

    @staticmethod
    def _book(row: sqlite3.Row) -> dict:
        return {"id": row["id"], "title": row["title"], "created_at": row["created_at"]}

    def add(self, title: str) -> dict:
        with self._connect() as conn:
            try:
                conn.execute(
                    "INSERT INTO books (title, created_at) VALUES (?, ?)",
                    (title, datetime.now(UTC).isoformat()),
                )
            except sqlite3.IntegrityError as exc:
                raise ConflictError(f"книга '{title}' уже есть в каталоге") from exc
            row = conn.execute(
                "SELECT * FROM books WHERE title = ?", (title,)
            ).fetchone()
        return self._book(row)

    def find_by_title(self, title: str) -> dict | None:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT * FROM books WHERE title = ?", (title,)
            ).fetchone()
        return self._book(row) if row else None

    def rename(self, title: str, new_title: str) -> dict:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT * FROM books WHERE title = ?", (title,)
            ).fetchone()
            if row is None:
                raise NotFoundError(f"книга '{title}' не найдена")
            try:
                conn.execute(
                    "UPDATE books SET title = ? WHERE id = ?", (new_title, row["id"])
                )
            except sqlite3.IntegrityError as exc:
                raise ConflictError(f"название '{new_title}' уже занято") from exc
            updated = conn.execute(
                "SELECT * FROM books WHERE id = ?", (row["id"],)
            ).fetchone()
        return self._book(updated)

    def delete(self, title: str) -> None:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT id FROM books WHERE title = ?", (title,)
            ).fetchone()
            if row is None:
                raise NotFoundError(f"книга '{title}' не найдена")
            conn.execute("DELETE FROM books WHERE id = ?", (row["id"],))

    def all(self) -> list[dict]:
        with self._connect() as conn:
            rows = conn.execute("SELECT * FROM books ORDER BY id").fetchall()
        return [self._book(r) for r in rows]

    def stats(self) -> dict:
        with self._connect() as conn:
            total = conn.execute("SELECT COUNT(*) FROM books").fetchone()[0]
        return {"total": total}

    def reset(self) -> None:
        with self._connect() as conn:
            conn.execute("DELETE FROM books")
            try:
                conn.execute("DELETE FROM sqlite_sequence WHERE name = 'books'")
            except sqlite3.OperationalError:
                pass  # sqlite_sequence ещё не создан (не было AUTOINCREMENT-вставок)

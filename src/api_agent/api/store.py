from datetime import UTC, datetime
from threading import Lock


class UserStore:
    """Потокобезопасное in-memory хранилище пользователей."""

    def __init__(self) -> None:
        self._users: dict[int, dict] = {}
        self._next_id = 1
        self._lock = Lock()

    def create(self, name: str, email: str | None) -> tuple[dict, bool]:
        with self._lock:
            duplicate = any(u["name"] == name for u in self._users.values())
            user = {
                "id": self._next_id,
                "name": name,
                "email": email,
                "status": "active",
                "created_at": datetime.now(UTC).isoformat(),
            }
            self._users[self._next_id] = user
            self._next_id += 1
            return dict(user), duplicate

    def find_by_name(self, name: str) -> list[dict]:
        with self._lock:
            return [dict(u) for u in self._users.values() if u["name"] == name]

    def update_status(self, name: str, status: str) -> dict | None:
        with self._lock:
            matches = [u for u in self._users.values() if u["name"] == name]
            if len(matches) != 1:
                return None
            matches[0]["status"] = status
            return dict(matches[0])

    def all(self) -> list[dict]:
        with self._lock:
            return [dict(u) for u in self._users.values()]

    def stats(self) -> dict:
        with self._lock:
            users = list(self._users.values())
        return {
            "total": len(users),
            "active": sum(1 for u in users if u["status"] == "active"),
            "blocked": sum(1 for u in users if u["status"] == "blocked"),
        }

    def reset(self) -> None:
        with self._lock:
            self._users.clear()
            self._next_id = 1

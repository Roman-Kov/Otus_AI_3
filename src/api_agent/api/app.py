from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

from .store import UserStore

app = FastAPI(title="Users API", version="0.1.0")
store = UserStore()

VALID_STATUSES = {"active", "blocked"}


class CreateUserIn(BaseModel):
    name: str = Field(min_length=1)
    email: str | None = None


class UpdateStatusIn(BaseModel):
    status: str


@app.post("/users", status_code=201)
def create_user(payload: CreateUserIn) -> dict:
    user, duplicate = store.create(payload.name, payload.email)
    return {**user, "duplicate": duplicate}


@app.get("/users")
def list_users() -> list[dict]:
    return store.all()


@app.get("/users/{name}")
def get_user_by_name(name: str) -> list[dict]:
    matches = store.find_by_name(name)
    if not matches:
        raise HTTPException(status_code=404, detail=f"пользователь '{name}' не найден")
    return matches


@app.patch("/users/{name}/status")
def update_user_status(name: str, payload: UpdateStatusIn) -> dict:
    if payload.status not in VALID_STATUSES:
        raise HTTPException(
            status_code=422, detail="status должен быть 'active' или 'blocked'"
        )
    matches = store.find_by_name(name)
    if not matches:
        raise HTTPException(status_code=404, detail=f"пользователь '{name}' не найден")
    if len(matches) > 1:
        raise HTTPException(
            status_code=409,
            detail={"message": f"имя '{name}' неоднозначно", "users": matches},
        )
    updated = store.update_status(name, payload.status)
    if updated is None:
        # Гонка: между find_by_name и update_status появился дубликат имени.
        raise HTTPException(
            status_code=409,
            detail={"message": f"имя '{name}' неоднозначно", "users": store.find_by_name(name)},
        )
    return updated


@app.get("/stats")
def get_stats() -> dict:
    return store.stats()

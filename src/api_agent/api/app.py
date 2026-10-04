from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field, field_validator

from .store import BookStore, ConflictError, NotFoundError

app = FastAPI(title="Books Catalog API", version="0.2.0")
store = BookStore()


def _reject_slash(v: str) -> str:
    # '/' запрещён: название адресуется через path-параметр
    if "/" in v:
        raise ValueError("название не может содержать символ '/'")
    return v


class BookTitleIn(BaseModel):
    title: str = Field(min_length=1)

    @field_validator("title")
    @classmethod
    def reject_slash(cls, v: str) -> str:
        return _reject_slash(v)


class NewTitleIn(BaseModel):
    new_title: str = Field(min_length=1)

    @field_validator("new_title")
    @classmethod
    def reject_slash(cls, v: str) -> str:
        return _reject_slash(v)


@app.post("/books", status_code=201)
def add_book(payload: BookTitleIn) -> dict:
    try:
        return store.add(payload.title)
    except ConflictError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@app.get("/books")
def list_books() -> list[dict]:
    return store.all()


@app.get("/books/{title}")
def get_book_by_title(title: str) -> dict:
    book = store.find_by_title(title)
    if book is None:
        raise HTTPException(status_code=404, detail=f"книга '{title}' не найдена")
    return book


@app.patch("/books/{title}")
def rename_book(title: str, payload: NewTitleIn) -> dict:
    try:
        return store.rename(title, payload.new_title)
    except NotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ConflictError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@app.delete("/books/{title}", status_code=204)
def delete_book(title: str) -> None:
    try:
        store.delete(title)
    except NotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@app.get("/stats")
def get_stats() -> dict:
    return store.stats()

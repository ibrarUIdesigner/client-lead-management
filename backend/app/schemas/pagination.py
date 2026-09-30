from pydantic import BaseModel


class Page[T](BaseModel):
    items: list[T]
    page: int
    limit: int
    total: int
    has_next: bool

"""Migration helpers that do nothing when the change is already in the database.

The first migration builds the schema from the current models, so a brand-new database
already has every later table and column before the later migrations run. These helpers
let each later migration work on both an old database (where it adds things) and a new one
(where it finds them already there).
"""

from __future__ import annotations

from typing import Any

import sqlalchemy as sa

from alembic import op


def _inspector() -> sa.Inspector:
    return sa.inspect(op.get_bind())


def has_table(name: str) -> bool:
    return name in _inspector().get_table_names()


def has_column(table: str, column: str) -> bool:
    if not has_table(table):
        return False
    return any(c["name"] == column for c in _inspector().get_columns(table))


def has_index(table: str, name: str) -> bool:
    if not has_table(table):
        return False
    return any(i["name"] == name for i in _inspector().get_indexes(table))


def add_column_if_missing(table: str, column: sa.Column) -> None:
    if not has_column(table, column.name):
        op.add_column(table, column)


def create_table_if_missing(name: str, *elements: Any, **kwargs: Any) -> None:
    if not has_table(name):
        op.create_table(name, *elements, **kwargs)


def create_index_if_missing(name: str, table: str, columns: list[str], **kwargs: Any) -> None:
    if not has_index(table, name):
        op.create_index(name, table, columns, **kwargs)

from enum import StrEnum

from sqlalchemy import CheckConstraint

from app.models.enums import enum_values


def status_constraint(table: str, column: str, enum_cls: type[StrEnum]) -> CheckConstraint:
    listed = ", ".join(f"'{value}'" for value in enum_values(enum_cls))
    return CheckConstraint(f"{column} IN ({listed})", name=f"ck_{table}_{column}")


def email_constraint(table: str, column: str) -> CheckConstraint:
    return CheckConstraint(
        f"{column} IS NULL OR {column} ~ '^[^@[:space:]]+@[^@[:space:]]+\\.[^@[:space:]]+$'",
        name=f"ck_{table}_{column}_email",
    )


def http_url_constraint(table: str, column: str) -> CheckConstraint:
    return CheckConstraint(
        f"{column} IS NULL OR {column} ~ '^https?://'",
        name=f"ck_{table}_{column}_url",
    )

from dataclasses import dataclass
from uuid import UUID

from sqlalchemy import String, asc, cast, desc, func, or_, select
from sqlalchemy.orm import Session

from app.models.lead import Lead

SORT_COLUMNS = {
    "created_at": Lead.created_at,
    "updated_at": Lead.updated_at,
    "business_name": Lead.business_name,
    "lead_score": Lead.lead_score,
    "lead_status": Lead.lead_status,
}


@dataclass
class LeadQuery:
    page: int = 1
    limit: int = 25
    q: str | None = None
    lead_status: str | None = None
    industry: str | None = None
    city: str | None = None
    country: str | None = None
    source: str | None = None
    website_status: str | None = None
    tag: str | None = None
    min_score: int | None = None
    sort: str = "created_at"
    direction: str = "desc"


def like_pattern(value: str) -> str:
    escaped = value.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
    return f"%{escaped}%"


class LeadRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def get(self, lead_id: UUID) -> Lead | None:
        return self.session.get(Lead, lead_id)

    def count(self, query: LeadQuery) -> int:
        filtered = self._filtered(query).subquery()
        total = self.session.scalar(select(func.count()).select_from(filtered))
        return int(total or 0)

    def list(self, query: LeadQuery) -> list[Lead]:
        column = SORT_COLUMNS[query.sort]
        ordered = asc(column) if query.direction == "asc" else desc(column)
        if query.sort == "lead_score":
            ordered = ordered.nulls_last()
        statement = (
            self._filtered(query)
            .order_by(ordered, Lead.id.asc())
            .offset((query.page - 1) * query.limit)
            .limit(query.limit)
        )
        return list(self.session.scalars(statement))

    def _filtered(self, query: LeadQuery):
        statement = select(Lead)
        if query.q:
            pattern = like_pattern(query.q)
            statement = statement.where(
                or_(
                    Lead.business_name.ilike(pattern, escape="\\"),
                    Lead.website_url.ilike(pattern, escape="\\"),
                    Lead.email.ilike(pattern, escape="\\"),
                    Lead.phone.ilike(pattern, escape="\\"),
                    Lead.city.ilike(pattern, escape="\\"),
                    Lead.industry.ilike(pattern, escape="\\"),
                    cast(Lead.tags, String).ilike(pattern, escape="\\"),
                )
            )
        if query.lead_status:
            statement = statement.where(Lead.lead_status == query.lead_status)
        if query.industry:
            statement = statement.where(
                Lead.industry.ilike(like_pattern(query.industry), escape="\\")
            )
        if query.city:
            statement = statement.where(Lead.city.ilike(like_pattern(query.city), escape="\\"))
        if query.country:
            statement = statement.where(
                Lead.country.ilike(like_pattern(query.country), escape="\\")
            )
        if query.source:
            statement = statement.where(Lead.source.ilike(like_pattern(query.source), escape="\\"))
        if query.website_status:
            statement = statement.where(Lead.website_status == query.website_status)
        if query.tag:
            statement = statement.where(Lead.tags.contains([query.tag]))
        if query.min_score is not None:
            statement = statement.where(Lead.lead_score >= query.min_score)
        return statement

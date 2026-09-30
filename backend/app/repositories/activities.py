from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.activity import Activity


class ActivityRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def add(
        self,
        lead_id: UUID,
        activity_type: str,
        title: str,
        description: str | None = None,
        details: dict[str, object] | None = None,
    ) -> Activity:
        activity = Activity(
            lead_id=lead_id,
            type=activity_type,
            title=title,
            description=description,
            details=details,
        )
        self.session.add(activity)
        return activity

    def list_for_lead(self, lead_id: UUID, limit: int = 50) -> list[Activity]:
        statement = (
            select(Activity)
            .where(Activity.lead_id == lead_id)
            .order_by(Activity.created_at.desc())
            .limit(limit)
        )
        return list(self.session.scalars(statement))

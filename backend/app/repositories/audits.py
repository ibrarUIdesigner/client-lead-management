from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.enums import AuditStatus
from app.models.website_audit import WebsiteAudit


class AuditRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def get(self, audit_id: UUID) -> WebsiteAudit | None:
        return self.session.get(WebsiteAudit, audit_id)

    def latest(self, lead_id: UUID) -> WebsiteAudit | None:
        statement = (
            select(WebsiteAudit)
            .where(WebsiteAudit.lead_id == lead_id)
            .order_by(WebsiteAudit.created_at.desc())
            .limit(1)
        )
        return self.session.scalars(statement).first()

    def list_for_lead(self, lead_id: UUID) -> list[WebsiteAudit]:
        statement = (
            select(WebsiteAudit)
            .where(WebsiteAudit.lead_id == lead_id)
            .order_by(WebsiteAudit.created_at.desc())
        )
        return list(self.session.scalars(statement))

    def get_active(self, lead_id: UUID) -> WebsiteAudit | None:
        statement = select(WebsiteAudit).where(
            WebsiteAudit.lead_id == lead_id,
            WebsiteAudit.status.in_((AuditStatus.PENDING.value, AuditStatus.RUNNING.value)),
        )
        return self.session.scalars(statement).first()

from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.errors import AppError
from app.models.design_guide import DesignGuide
from app.models.enums import AuditStatus, MockupStatus
from app.models.lead import Lead
from app.models.mockup import Mockup
from app.models.website_audit import WebsiteAudit
from app.schemas.design_guides import MockupCreate, MockupCreated, MockupGuideRead
from app.services.design_markdown import (
    build_brief,
    parse_markdown,
    snapshot_choice,
    verified_finding_lines,
)


class MockupService:
    """Records a homepage brief. It does not call an image or text model."""

    def __init__(self, session: Session) -> None:
        self.session = session

    def create(self, data: MockupCreate) -> MockupCreated:
        lead = self.session.get(Lead, data.lead_id)
        if lead is None:
            raise AppError(
                code="LEAD_NOT_FOUND",
                message="That lead could not be found.",
                status_code=404,
            )
        source = self._source(data)
        try:
            mode = snapshot_choice(
                mode=data.guide_mode,
                has_saved_snapshot=bool(source and source.design_guide_snapshot),
                has_selected_guide=data.design_guide_id is not None,
            )
        except ValueError as exc:
            raise AppError(code="VALIDATION_ERROR", message=str(exc), status_code=422) from exc

        guide_id: UUID | None = None
        guide_name: str | None = None
        snapshot: str | None = None
        if mode == "keep" and source is not None:
            guide_id = source.design_guide_id
            guide_name = source.design_guide_name
            snapshot = source.design_guide_snapshot
        elif mode == "selected" and data.design_guide_id is not None:
            guide = self.session.get(DesignGuide, data.design_guide_id)
            if guide is None:
                raise AppError(
                    code="GUIDE_NOT_FOUND",
                    message="That design guide could not be found.",
                    status_code=404,
                )
            guide_id = guide.id
            guide_name = guide.name
            snapshot = guide.content

        audit = self.session.scalar(
            select(WebsiteAudit)
            .where(
                WebsiteAudit.lead_id == lead.id,
                WebsiteAudit.status == AuditStatus.COMPLETED.value,
            )
            .order_by(WebsiteAudit.completed_at.desc())
        )
        findings = verified_finding_lines(
            audit.raw_analysis if audit is not None else None,
            completed=audit is not None,
        )
        version = int(
            self.session.scalar(select(func.max(Mockup.version)).where(Mockup.lead_id == lead.id))
            or 0
        )
        mockup = Mockup(
            lead_id=lead.id,
            audit_id=audit.id if audit is not None else None,
            title="Homepage concept",
            status=MockupStatus.READY.value,
            prompt=build_brief(
                business_name=lead.business_name,
                city=lead.city,
                industry=lead.industry,
                website_url=lead.website_url,
                description=lead.description,
                findings=findings,
                requirements=data.requirements,
                guidance=snapshot,
            ),
            provider="brief",
            version=version + 1,
            notes="Design brief saved. No image was generated.",
            completed_at=datetime.now(UTC),
            design_guide_id=guide_id,
            design_guide_name=guide_name,
            design_guide_snapshot=snapshot,
        )
        self.session.add(mockup)
        self.session.flush()
        return MockupCreated.from_mockup(mockup)

    def guide_snapshot(self, mockup_id: UUID) -> MockupGuideRead:
        mockup = self.session.get(Mockup, mockup_id)
        if mockup is None:
            raise AppError(
                code="MOCKUP_NOT_FOUND",
                message="That mockup could not be found.",
                status_code=404,
            )
        snapshot = mockup.design_guide_snapshot or ""
        return MockupGuideRead(
            id=mockup.id,
            design_guide_id=mockup.design_guide_id,
            design_guide_name=mockup.design_guide_name,
            design_guide_snapshot=mockup.design_guide_snapshot,
            blocks=parse_markdown(snapshot) if snapshot else [],
        )

    def _source(self, data: MockupCreate) -> Mockup | None:
        if data.source_mockup_id is None:
            if data.guide_mode == "keep":
                raise AppError(
                    code="VALIDATION_ERROR",
                    message="Choose the mockup whose saved design guide should be kept.",
                    status_code=422,
                )
            return None
        source = self.session.get(Mockup, data.source_mockup_id)
        if source is None or source.lead_id != data.lead_id:
            raise AppError(
                code="MOCKUP_NOT_FOUND",
                message="That mockup could not be found.",
                status_code=404,
            )
        return source

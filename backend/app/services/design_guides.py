from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.core.config import Settings
from app.core.errors import AppError
from app.models.design_guide import DesignGuide
from app.schemas.design_guides import (
    DesignGuideList,
    DesignGuideRead,
    DesignGuideSummary,
    DesignGuideTemplate,
    DesignGuideWrite,
)
from app.services.design_markdown import STARTER_TEMPLATE, parse_markdown, read_markdown_upload


class DesignGuideService:
    """Guides belong to this local workspace. The app has no separate user accounts."""

    def __init__(self, session: Session, settings: Settings) -> None:
        self.session = session
        self.settings = settings

    def list_guides(self, *, query: str | None, tag: str | None) -> DesignGuideList:
        statement = select(DesignGuide).order_by(DesignGuide.updated_at.desc())
        needle = (query or "").strip()
        if needle:
            like = f"%{needle}%"
            statement = statement.where(
                or_(
                    DesignGuide.name.ilike(like),
                    DesignGuide.description.ilike(like),
                    DesignGuide.content.ilike(like),
                )
            )
        if tag and tag.strip():
            statement = statement.where(DesignGuide.tags.contains([tag.strip()]))
        guides = list(self.session.scalars(statement))
        tags = sorted({item for guide in self._all() for item in guide.tags})
        return DesignGuideList(items=[_summary(guide) for guide in guides], tags=tags)

    def get_guide(self, guide_id: UUID) -> DesignGuideRead:
        return _read(self._require(guide_id))

    def template(self) -> DesignGuideTemplate:
        return DesignGuideTemplate(
            content=STARTER_TEMPLATE,
            blocks=parse_markdown(STARTER_TEMPLATE),
        )

    def create_guide(self, data: DesignGuideWrite) -> DesignGuideRead:
        self._check_size(data.content)
        guide = DesignGuide(
            name=data.name,
            description=data.description,
            tags=data.tags,
            content=data.content,
        )
        self.session.add(guide)
        self.session.flush()
        return _read(guide)

    def create_from_upload(
        self,
        *,
        name: str,
        description: str | None,
        tags: list[str],
        filename: str | None,
        payload: bytes,
    ) -> DesignGuideRead:
        try:
            content = read_markdown_upload(
                filename,
                payload,
                max_bytes=self.settings.design_md_max_bytes,
            )
        except ValueError as exc:
            raise AppError(code="VALIDATION_ERROR", message=str(exc), status_code=422) from exc
        data = DesignGuideWrite(
            name=name,
            description=description,
            tags=tags,
            content=content,
        )
        return self.create_guide(data)

    def update_guide(self, guide_id: UUID, data: DesignGuideWrite) -> DesignGuideRead:
        guide = self._require(guide_id)
        self._check_size(data.content)
        guide.name = data.name
        guide.description = data.description
        guide.tags = data.tags
        guide.content = data.content
        guide.updated_at = datetime.now(UTC)
        self.session.flush()
        return _read(guide)

    def delete_guide(self, guide_id: UUID) -> None:
        guide = self._require(guide_id)
        self.session.delete(guide)

    def _require(self, guide_id: UUID) -> DesignGuide:
        guide = self.session.get(DesignGuide, guide_id)
        if guide is None:
            raise AppError(
                code="GUIDE_NOT_FOUND",
                message="That design guide could not be found.",
                status_code=404,
            )
        return guide

    def _all(self) -> list[DesignGuide]:
        return list(self.session.scalars(select(DesignGuide)))

    def _check_size(self, content: str) -> None:
        size = len(content.encode("utf-8"))
        if size > self.settings.design_md_max_bytes:
            raise AppError(
                code="VALIDATION_ERROR",
                message=f"That guide is larger than {self.settings.design_md_max_bytes} bytes.",
                status_code=422,
            )


def _summary(guide: DesignGuide) -> DesignGuideSummary:
    return DesignGuideSummary(
        id=guide.id,
        name=guide.name,
        description=guide.description,
        tags=list(guide.tags or []),
        updated_at=guide.updated_at,
    )


def _read(guide: DesignGuide) -> DesignGuideRead:
    return DesignGuideRead(
        id=guide.id,
        name=guide.name,
        description=guide.description,
        tags=list(guide.tags or []),
        content=guide.content,
        created_at=guide.created_at,
        updated_at=guide.updated_at,
        blocks=parse_markdown(guide.content),
    )

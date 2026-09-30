from uuid import UUID

from sqlalchemy.orm import Session

from app.core.errors import AppError
from app.models.enums import LeadStatus
from app.models.lead import Lead
from app.repositories.activities import ActivityRepository
from app.repositories.leads import LeadQuery, LeadRepository
from app.schemas.leads import (
    ActivityRead,
    BulkLeadResult,
    BulkLeadUpdate,
    LeadCreate,
    LeadDetail,
    LeadImportResult,
    LeadRead,
    LeadUpdate,
)
from app.schemas.pagination import Page
from app.schemas.values import normalize_tags, slugify
from app.services.lead_csv import parse_lead_csv
from app.services.persistence import flush_or_reject


class LeadService:
    def __init__(self, session: Session) -> None:
        self.session = session
        self.leads = LeadRepository(session)
        self.activities = ActivityRepository(session)

    def list_leads(self, query: LeadQuery) -> Page[LeadRead]:
        total = self.leads.count(query)
        rows = self.leads.list(query)
        return Page(
            items=[LeadRead.model_validate(row) for row in rows],
            page=query.page,
            limit=query.limit,
            total=total,
            has_next=query.page * query.limit < total,
        )

    def get(self, lead_id: UUID) -> LeadDetail:
        lead = self._require(lead_id)
        return LeadDetail(
            **LeadRead.model_validate(lead).model_dump(),
            activities=[
                ActivityRead.model_validate(activity)
                for activity in self.activities.list_for_lead(lead_id)
            ],
        )

    def create(self, data: LeadCreate, *, imported: bool = False) -> LeadRead:
        lead = self._build(data)
        self.session.add(lead)
        flush_or_reject(self.session)
        self.activities.add(
            lead.id,
            "lead_imported" if imported else "lead_created",
            "Lead imported" if imported else "Lead created",
            description=lead.business_name,
        )
        self.session.refresh(lead)
        return LeadRead.model_validate(lead)

    def update(self, lead_id: UUID, data: LeadUpdate) -> LeadRead:
        lead = self._require(lead_id)
        changes = data.model_dump(exclude_unset=True)
        if "business_name" in changes and not changes["business_name"]:
            raise AppError(
                code="VALIDATION_ERROR",
                message="Enter the business name.",
                status_code=422,
            )
        previous_status = lead.lead_status
        if isinstance(changes.get("lead_status"), LeadStatus):
            changes["lead_status"] = changes["lead_status"].value
        for key, value in changes.items():
            setattr(lead, key, value)
        if "business_name" in changes:
            lead.slug = slugify(lead.business_name)
        flush_or_reject(self.session)
        self._record_update(lead, changes, previous_status)
        self.session.refresh(lead)
        return LeadRead.model_validate(lead)

    def update_status(self, lead_id: UUID, lead_status: LeadStatus) -> LeadRead:
        return self.update(lead_id, LeadUpdate(lead_status=lead_status))

    def delete(self, lead_id: UUID) -> None:
        lead = self._require(lead_id)
        self.session.delete(lead)

    def bulk_update(self, data: BulkLeadUpdate) -> BulkLeadResult:
        ids = list(dict.fromkeys(data.ids))
        found: list[Lead] = []
        missing: list[str] = []
        for lead_id in ids:
            lead = self.leads.get(lead_id)
            if lead is None:
                missing.append(str(lead_id))
            else:
                found.append(lead)
        if missing:
            raise AppError(
                code="LEAD_NOT_FOUND",
                message="Some leads could not be found.",
                status_code=404,
                details={"ids": missing},
            )

        for lead in found:
            if data.lead_status is not None and lead.lead_status != data.lead_status.value:
                previous = lead.lead_status
                lead.lead_status = data.lead_status.value
                self.activities.add(
                    lead.id,
                    "status_changed",
                    "Status changed",
                    description=f"{previous} to {lead.lead_status}",
                    details={"from": previous, "to": lead.lead_status},
                )
            if data.add_tags:
                merged = _merge_tags(list(lead.tags or []), data.add_tags)
                if merged != list(lead.tags or []):
                    lead.tags = merged
                    self.activities.add(lead.id, "tags_updated", "Tags updated")
        flush_or_reject(self.session)
        for lead in found:
            self.session.refresh(lead)
        return BulkLeadResult(items=[LeadRead.model_validate(lead) for lead in found])

    def import_csv(self, content: str, *, dry_run: bool) -> LeadImportResult:
        valid, invalid = parse_lead_csv(content)
        created = 0
        if not dry_run:
            for row in valid:
                self.create(row.lead, imported=True)
                created += 1
        return LeadImportResult(
            dry_run=dry_run,
            created=created,
            valid_rows=[row.preview for row in valid],
            invalid_rows=invalid,
        )

    def _require(self, lead_id: UUID) -> Lead:
        lead = self.leads.get(lead_id)
        if lead is None:
            raise AppError(
                code="LEAD_NOT_FOUND",
                message="That lead could not be found.",
                status_code=404,
            )
        return lead

    def _build(self, data: LeadCreate) -> Lead:
        return Lead(
            business_name=data.business_name,
            slug=slugify(data.business_name),
            industry=data.industry,
            description=data.description,
            country=data.country,
            city=data.city,
            website_url=data.website_url,
            email=data.email,
            phone=data.phone,
            linkedin_url=data.linkedin_url,
            instagram_url=data.instagram_url,
            facebook_url=data.facebook_url,
            google_maps_url=data.google_maps_url,
            lead_status=data.lead_status.value,
            source=data.source,
            tags=data.tags,
            notes=data.notes,
        )

    def _record_update(self, lead: Lead, changes: dict[str, object], previous_status: str) -> None:
        status_changed = "lead_status" in changes and lead.lead_status != previous_status
        other_changes = any(key != "lead_status" for key in changes)
        if status_changed:
            self.activities.add(
                lead.id,
                "status_changed",
                "Status changed",
                description=f"{previous_status} to {lead.lead_status}",
                details={"from": previous_status, "to": lead.lead_status},
            )
        if other_changes:
            self.activities.add(lead.id, "lead_updated", "Lead updated")


def _merge_tags(current: list[str], extra: list[str]) -> list[str]:
    return normalize_tags([*current, *extra])

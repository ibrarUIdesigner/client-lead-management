from typing import Literal
from uuid import UUID

from fastapi import APIRouter, Query, UploadFile
from fastapi.responses import Response

from app.api.deps import SessionDep
from app.core.errors import AppError
from app.models.enums import LeadStatus
from app.repositories.leads import LeadQuery
from app.schemas.leads import (
    BulkLeadResult,
    BulkLeadUpdate,
    LeadCreate,
    LeadDetail,
    LeadImportResult,
    LeadRead,
    LeadStatusUpdate,
    LeadUpdate,
)
from app.schemas.pagination import Page
from app.services.leads import LeadService

router = APIRouter(tags=["leads"])

MAX_CSV_BYTES = 1_000_000


def _clean(value: str | None) -> str | None:
    if value is None:
        return None
    stripped = value.strip()
    return stripped or None


@router.post("/leads/import", response_model=LeadImportResult)
async def import_leads(
    file: UploadFile,
    session: SessionDep,
    dry_run: bool = False,
) -> LeadImportResult:
    raw = await file.read(MAX_CSV_BYTES + 1)
    if len(raw) > MAX_CSV_BYTES:
        raise AppError(
            code="FILE_TOO_LARGE",
            message="The file is larger than 1 MB.",
            status_code=400,
        )
    try:
        content = raw.decode("utf-8-sig")
    except UnicodeDecodeError:
        raise AppError(
            code="CSV_INVALID",
            message="Save the file as UTF-8 and try again.",
            status_code=400,
        ) from None
    return LeadService(session).import_csv(content, dry_run=dry_run)


@router.patch("/leads/bulk", response_model=BulkLeadResult)
def bulk_update_leads(
    data: BulkLeadUpdate,
    session: SessionDep,
) -> BulkLeadResult:
    return LeadService(session).bulk_update(data)


@router.post("/leads", response_model=LeadRead, status_code=201)
def create_lead(data: LeadCreate, session: SessionDep) -> LeadRead:
    return LeadService(session).create(data)


@router.get("/leads", response_model=Page[LeadRead])
def list_leads(
    session: SessionDep,
    page: int = Query(default=1, ge=1),
    limit: int = Query(default=25, ge=1, le=100),
    q: str | None = Query(default=None, max_length=200),
    lead_status: LeadStatus | None = None,
    industry: str | None = Query(default=None, max_length=120),
    city: str | None = Query(default=None, max_length=120),
    country: str | None = Query(default=None, max_length=120),
    source: str | None = Query(default=None, max_length=120),
    website_status: str | None = Query(default=None, max_length=32),
    tag: str | None = Query(default=None, max_length=50),
    min_score: int | None = Query(default=None, ge=0, le=100),
    sort: Literal["created_at", "business_name", "lead_score", "lead_status", "updated_at"] = (
        "created_at"
    ),
    direction: Literal["asc", "desc"] = "desc",
) -> Page[LeadRead]:
    query = LeadQuery(
        page=page,
        limit=limit,
        q=_clean(q),
        lead_status=lead_status.value if lead_status else None,
        industry=_clean(industry),
        city=_clean(city),
        country=_clean(country),
        source=_clean(source),
        website_status=_clean(website_status),
        tag=_clean(tag),
        min_score=min_score,
        sort=sort,
        direction=direction,
    )
    return LeadService(session).list_leads(query)


@router.get("/leads/{lead_id}", response_model=LeadDetail)
def get_lead(lead_id: UUID, session: SessionDep) -> LeadDetail:
    return LeadService(session).get(lead_id)


@router.patch("/leads/{lead_id}", response_model=LeadRead)
def update_lead(
    lead_id: UUID,
    data: LeadUpdate,
    session: SessionDep,
) -> LeadRead:
    return LeadService(session).update(lead_id, data)


@router.patch("/leads/{lead_id}/status", response_model=LeadRead)
def update_lead_status(
    lead_id: UUID,
    data: LeadStatusUpdate,
    session: SessionDep,
) -> LeadRead:
    return LeadService(session).update_status(lead_id, data.lead_status)


@router.delete("/leads/{lead_id}", status_code=204)
def delete_lead(lead_id: UUID, session: SessionDep) -> Response:
    LeadService(session).delete(lead_id)
    return Response(status_code=204)

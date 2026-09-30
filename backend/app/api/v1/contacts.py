from uuid import UUID

from fastapi import APIRouter
from fastapi.responses import Response

from app.api.deps import SessionDep
from app.schemas.contacts import ContactCreate, ContactRead, ContactUpdate
from app.services.contacts import ContactService

router = APIRouter(tags=["contacts"])


@router.get("/leads/{lead_id}/contacts", response_model=list[ContactRead])
def list_contacts(lead_id: UUID, session: SessionDep) -> list[ContactRead]:
    return ContactService(session).list_for_lead(lead_id)


@router.post("/leads/{lead_id}/contacts", response_model=ContactRead, status_code=201)
def create_contact(
    lead_id: UUID,
    data: ContactCreate,
    session: SessionDep,
) -> ContactRead:
    return ContactService(session).create(lead_id, data)


@router.patch("/contacts/{contact_id}", response_model=ContactRead)
def update_contact(
    contact_id: UUID,
    data: ContactUpdate,
    session: SessionDep,
) -> ContactRead:
    return ContactService(session).update(contact_id, data)


@router.delete("/contacts/{contact_id}", status_code=204)
def delete_contact(contact_id: UUID, session: SessionDep) -> Response:
    ContactService(session).delete(contact_id)
    return Response(status_code=204)

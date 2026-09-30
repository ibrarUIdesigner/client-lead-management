from uuid import UUID

from sqlalchemy.orm import Session

from app.core.errors import AppError
from app.models.contact import Contact
from app.repositories.activities import ActivityRepository
from app.repositories.contacts import ContactRepository
from app.repositories.leads import LeadRepository
from app.schemas.contacts import ContactCreate, ContactRead, ContactUpdate
from app.services.persistence import flush_or_reject


class ContactService:
    def __init__(self, session: Session) -> None:
        self.session = session
        self.contacts = ContactRepository(session)
        self.leads = LeadRepository(session)
        self.activities = ActivityRepository(session)

    def list_for_lead(self, lead_id: UUID) -> list[ContactRead]:
        self._require_lead(lead_id)
        rows = self.contacts.list_for_lead(lead_id)
        return [ContactRead.model_validate(contact) for contact in rows]

    def create(self, lead_id: UUID, data: ContactCreate) -> ContactRead:
        self._require_lead(lead_id)
        if data.is_primary:
            self.contacts.clear_primary(lead_id)
        contact = Contact(
            lead_id=lead_id,
            name=data.name,
            job_title=data.job_title,
            email=data.email,
            phone=data.phone,
            linkedin_url=data.linkedin_url,
            is_primary=data.is_primary,
        )
        self.session.add(contact)
        flush_or_reject(self.session)
        self.activities.add(
            lead_id,
            "contact_added",
            "Contact added",
            description=data.name,
        )
        self.session.refresh(contact)
        return ContactRead.model_validate(contact)

    def update(self, contact_id: UUID, data: ContactUpdate) -> ContactRead:
        contact = self._require(contact_id)
        changes = data.model_dump(exclude_unset=True)
        if "name" in changes and not changes["name"]:
            raise AppError(
                code="VALIDATION_ERROR",
                message="Enter the contact name.",
                status_code=422,
            )
        if changes.get("is_primary") is True:
            self.contacts.clear_primary(contact.lead_id, except_id=contact.id)
        for key, value in changes.items():
            setattr(contact, key, value)
        flush_or_reject(self.session)
        self.activities.add(
            contact.lead_id,
            "contact_updated",
            "Contact updated",
            description=contact.name,
        )
        self.session.refresh(contact)
        return ContactRead.model_validate(contact)

    def delete(self, contact_id: UUID) -> None:
        contact = self._require(contact_id)
        name = contact.name
        lead_id = contact.lead_id
        self.session.delete(contact)
        self.activities.add(lead_id, "contact_removed", "Contact removed", description=name)

    def _require_lead(self, lead_id: UUID) -> None:
        if self.leads.get(lead_id) is None:
            raise AppError(
                code="LEAD_NOT_FOUND",
                message="That lead could not be found.",
                status_code=404,
            )

    def _require(self, contact_id: UUID) -> Contact:
        contact = self.contacts.get(contact_id)
        if contact is None:
            raise AppError(
                code="CONTACT_NOT_FOUND",
                message="That contact could not be found.",
                status_code=404,
            )
        return contact

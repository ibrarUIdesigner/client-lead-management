from uuid import UUID

from sqlalchemy import select, update
from sqlalchemy.orm import Session

from app.models.contact import Contact


class ContactRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def get(self, contact_id: UUID) -> Contact | None:
        return self.session.get(Contact, contact_id)

    def list_for_lead(self, lead_id: UUID) -> list[Contact]:
        statement = (
            select(Contact)
            .where(Contact.lead_id == lead_id)
            .order_by(Contact.is_primary.desc(), Contact.created_at.asc())
        )
        return list(self.session.scalars(statement))

    def clear_primary(self, lead_id: UUID, except_id: UUID | None = None) -> None:
        statement = update(Contact).where(Contact.lead_id == lead_id)
        if except_id is not None:
            statement = statement.where(Contact.id != except_id)
        self.session.execute(statement.values(is_primary=False))

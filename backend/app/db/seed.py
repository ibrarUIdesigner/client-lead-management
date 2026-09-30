from sqlalchemy import func, select

from app.core.config import get_settings
from app.db.session import create_db_engine, create_session_factory
from app.models import Activity, Contact, Followup, Lead
from app.models.enums import FollowupStatus, LeadStatus


def seed() -> None:
    engine = create_db_engine(get_settings().database_url)
    session_factory = create_session_factory(engine)
    with session_factory() as session:
        existing = session.scalar(select(func.count()).select_from(Lead))
        if existing:
            return

        cafe = Lead(
            business_name="Northwind Cafe",
            industry="Cafe",
            city="Portland",
            country="United States",
            website_url="https://northwind.example",
            email="hello@northwind.example",
            lead_status=LeadStatus.NEW.value,
            source="manual",
            tags=["cafe", "website"],
            notes="Homepage is hard to read on a phone.",
        )
        dental = Lead(
            business_name="Harbor Dental",
            industry="Clinic",
            city="Seattle",
            country="United States",
            website_url="https://harbordental.example",
            lead_status=LeadStatus.QUALIFIED.value,
            source="maps",
            tags=["clinic"],
        )
        studio = Lead(
            business_name="Lumen Studio",
            industry="Studio",
            city="Austin",
            country="United States",
            website_url="https://lumenstudio.example",
            email="studio@lumen.example",
            lead_status=LeadStatus.CONTACTED.value,
            source="referral",
            tags=["studio"],
        )
        session.add_all([cafe, dental, studio])
        session.flush()

        contact = Contact(
            lead_id=studio.id,
            name="Avery Chen",
            job_title="Owner",
            email="avery@lumen.example",
            is_primary=True,
        )
        followup = Followup(
            lead_id=studio.id,
            scheduled_for=func.now(),
            type="email",
            status=FollowupStatus.SCHEDULED.value,
            notes="Ask whether the homepage concept was useful.",
        )
        activity = Activity(
            lead_id=studio.id,
            type="outreach",
            title="Marked contacted",
            description="First note was sent by hand.",
        )
        session.add_all([contact, followup, activity])
        session.commit()
    engine.dispose()


if __name__ == "__main__":
    seed()

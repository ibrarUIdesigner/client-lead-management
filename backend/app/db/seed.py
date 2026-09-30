from datetime import UTC, datetime, timedelta

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.db.session import create_db_engine, create_session_factory
from app.models import (
    Activity,
    BrandProfile,
    Contact,
    Followup,
    Lead,
    Mockup,
    OutreachMessage,
    OutreachTemplate,
    WebsiteAudit,
)
from app.models.enums import (
    AuditStatus,
    FollowupStatus,
    LeadStatus,
    MockupStatus,
    OutreachStatus,
)

SAMPLE_SOURCE = "sample"


def seed() -> int:
    engine = create_db_engine(get_settings().database_url)
    session_factory = create_session_factory(engine)
    with session_factory() as session:
        existing = session.scalar(select(func.count()).select_from(Lead))
        if existing:
            engine.dispose()
            return 0

        now = datetime.now(UTC)
        leads = _leads(now)
        session.add_all(leads)
        session.flush()
        by_name = {lead.business_name: lead for lead in leads}
        _contacts(session, by_name)
        _activities(session, by_name, now)
        audits = _audits(session, by_name, now)
        _brands(session, by_name)
        _mockups(session, by_name, audits, now)
        templates = _templates(session)
        _outreach(session, by_name, templates, now)
        _followups(session, by_name, now)
        session.commit()
        count = len(leads)
    engine.dispose()
    return count


def _leads(now: datetime) -> list[Lead]:
    rows: list[tuple[object, ...]] = [
        (
            "Maple & Rye Bakery",
            "Bakery",
            "Portland",
            LeadStatus.NEW,
            28,
            None,
            None,
            2,
            ["bakery", "local"],
            "Found on a neighborhood map. Site looks dated.",
            "hello@mapleandrye.example",
            "+1 503 555 0108",
            "https://mapleandrye.example",
        ),
        (
            "Cedar Street Books",
            "Retail",
            "Seattle",
            LeadStatus.NEW,
            22,
            None,
            None,
            4,
            ["retail", "books"],
            "Independent shop. No online ordering.",
            "books@cedarstreet.example",
            "+1 206 555 0144",
            "https://cedarstreetbooks.example",
        ),
        (
            "Brightside Tutoring",
            "Education",
            "Denver",
            LeadStatus.NEW,
            31,
            None,
            None,
            1,
            ["education"],
            "Owner asked for examples before a call.",
            "hi@brightsidetutoring.example",
            "+1 303 555 0170",
            "https://brightsidetutoring.example",
        ),
        (
            "Harbor Dental",
            "Clinic",
            "Seattle",
            LeadStatus.QUALIFIED,
            58,
            "pending",
            None,
            6,
            ["clinic", "healthcare"],
            "Front desk said the site is hard to update.",
            "frontdesk@harbordental.example",
            "+1 206 555 0192",
            "https://harbordental.example",
        ),
        (
            "Lumen Studio",
            "Studio",
            "Austin",
            LeadStatus.QUALIFIED,
            64,
            None,
            None,
            8,
            ["studio", "photography"],
            "Portfolio is a single scrolling page.",
            "studio@lumen.example",
            "+1 512 555 0116",
            "https://lumenstudio.example",
        ),
        (
            "Northwind Cafe",
            "Cafe",
            "Portland",
            LeadStatus.AUDIT_PENDING,
            46,
            "pending",
            None,
            3,
            ["cafe", "website"],
            "Homepage is hard to read on a phone.",
            "hello@northwind.example",
            "+1 503 555 0133",
            "https://northwind.example",
        ),
        (
            "Oak & Iron Fitness",
            "Gym",
            "Chicago",
            LeadStatus.AUDIT_COMPLETE,
            70,
            "analyzed",
            38,
            9,
            ["gym", "mobile"],
            "Class schedule is buried. Strong outreach candidate.",
            "info@oakandiron.example",
            "+1 312 555 0188",
            "https://oakandiron.example",
        ),
        (
            "Field & Fern Florist",
            "Florist",
            "Denver",
            LeadStatus.AUDIT_COMPLETE,
            30,
            "missing",
            None,
            5,
            ["florist", "no-website"],
            "Instagram only. No website address on the listing.",
            "orders@fieldandfern.example",
            "+1 303 555 0161",
            None,
        ),
        (
            "Sable Law",
            "Legal",
            "Boston",
            LeadStatus.MOCKUP_PENDING,
            61,
            "analyzed",
            52,
            11,
            ["legal"],
            "Practice site has no clear way to book a consult.",
            "office@sablelaw.example",
            "+1 617 555 0104",
            "https://sablelaw.example",
        ),
        (
            "Kindred Salon",
            "Salon",
            "Austin",
            LeadStatus.MOCKUP_READY,
            74,
            "analyzed",
            44,
            12,
            ["salon", "booking"],
            "Mockup is ready to send with the first note.",
            "hello@kindredsalon.example",
            "+1 512 555 0199",
            "https://kindredsalon.example",
        ),
        (
            "Redbird Bicycles",
            "Retail",
            "Portland",
            LeadStatus.CONTACTED,
            68,
            "analyzed",
            49,
            14,
            ["retail", "bicycles"],
            "Sent the homepage concept on Tuesday.",
            "shop@redbird.example",
            "+1 503 555 0127",
            "https://redbirdbicycles.example",
        ),
        (
            "Glasshouse Hotel",
            "Hospitality",
            "Chicago",
            LeadStatus.CONTACTED,
            57,
            "analyzed",
            63,
            16,
            ["hotel"],
            "General manager asked us to follow up next week.",
            "stay@glasshouse.example",
            "+1 312 555 0155",
            "https://glasshousehotel.example",
        ),
        (
            "Pebble Pediatrics",
            "Clinic",
            "Seattle",
            LeadStatus.FOLLOW_UP,
            72,
            "analyzed",
            41,
            18,
            ["clinic", "follow-up"],
            "Follow-up is overdue. They opened the first email.",
            "hello@pebblepediatrics.example",
            "+1 206 555 0180",
            "https://pebblepediatrics.example",
        ),
        (
            "Marlowe Interiors",
            "Studio",
            "Denver",
            LeadStatus.FOLLOW_UP,
            66,
            "analyzed",
            55,
            13,
            ["interiors"],
            "Second note is due this afternoon.",
            "studio@marlowe.example",
            "+1 303 555 0112",
            "https://marloweinteriors.example",
        ),
        (
            "Summit Auto",
            "Automotive",
            "Denver",
            LeadStatus.REPLIED,
            77,
            "analyzed",
            36,
            20,
            ["auto"],
            "Owner replied and asked what a refresh would cost.",
            "service@summitauto.example",
            "+1 303 555 0194",
            "https://summitauto.example",
        ),
        (
            "Hearth & Hide",
            "Restaurant",
            "Portland",
            LeadStatus.MEETING,
            81,
            "analyzed",
            47,
            22,
            ["restaurant"],
            "Menu is a PDF. Meeting set to walk through a new homepage.",
            "hello@hearthandhide.example",
            "+1 503 555 0166",
            "https://hearthandhide.example",
        ),
        (
            "Atlas Accounting",
            "Professional services",
            "Boston",
            LeadStatus.PROPOSAL,
            84,
            "analyzed",
            58,
            25,
            ["accounting", "proposal"],
            "Proposal sent for a five-page site and ongoing updates.",
            "partners@atlasaccounting.example",
            "+1 617 555 0138",
            "https://atlasaccounting.example",
        ),
        (
            "Willow Yoga",
            "Wellness",
            "Austin",
            LeadStatus.WON,
            88,
            "analyzed",
            71,
            30,
            ["wellness", "won"],
            "Signed for a new site. Kickoff is next Monday.",
            "hello@willowyoga.example",
            "+1 512 555 0148",
            "https://willowyoga.example",
        ),
        (
            "Drift Goods",
            "Retail",
            "Chicago",
            LeadStatus.LOST,
            24,
            "analyzed",
            33,
            28,
            ["retail"],
            "They hired a nephew to rebuild the site.",
            "hi@driftgoods.example",
            "+1 312 555 0177",
            "https://driftgoods.example",
        ),
        (
            "Copper Kettle Tea",
            "Cafe",
            "Seattle",
            LeadStatus.NOT_INTERESTED,
            19,
            None,
            None,
            15,
            ["cafe"],
            "Owner said they are happy with the current site.",
            "tea@copperkettle.example",
            "+1 206 555 0120",
            "https://copperkettle.example",
        ),
    ]

    leads: list[Lead] = []
    for row in rows:
        (
            name,
            industry,
            city,
            status,
            score,
            website_status,
            quality,
            days_ago,
            tags,
            notes,
            email,
            phone,
            website,
        ) = row
        contacted = status in {
            LeadStatus.CONTACTED,
            LeadStatus.FOLLOW_UP,
            LeadStatus.REPLIED,
            LeadStatus.MEETING,
            LeadStatus.PROPOSAL,
            LeadStatus.WON,
            LeadStatus.LOST,
            LeadStatus.NOT_INTERESTED,
        }
        followup_at = None
        if name == "Pebble Pediatrics":
            followup_at = now - timedelta(days=1)
        elif name == "Marlowe Interiors":
            followup_at = now + timedelta(hours=4)
        elif name == "Redbird Bicycles":
            followup_at = now + timedelta(days=3)
        elif name == "Glasshouse Hotel":
            followup_at = now + timedelta(days=6)
        created = now - timedelta(days=int(days_ago))
        leads.append(
            Lead(
                business_name=str(name),
                slug=str(name).lower().replace(" ", "-").replace("&", "and"),
                industry=str(industry),
                description=f"{name} is a {str(industry).lower()} in {city}.",
                country="United States",
                city=str(city),
                website_url=None if website is None else str(website),
                website_status=None if website_status is None else str(website_status),
                website_quality_score=None if quality is None else int(quality),
                email=str(email),
                phone=str(phone),
                linkedin_url=f"https://www.linkedin.com/company/{str(name).split()[0].lower()}",
                instagram_url=f"https://www.instagram.com/{str(name).split()[0].lower()}",
                lead_score=int(score),
                lead_status=status.value,
                source=SAMPLE_SOURCE,
                tags=list(tags),
                notes=str(notes),
                created_at=created,
                updated_at=now - timedelta(hours=int(days_ago)),
                last_contacted_at=(now - timedelta(days=2)) if contacted else None,
                next_followup_at=followup_at,
            )
        )
    return leads


def _contacts(session: Session, leads: dict[str, Lead]) -> None:
    people: dict[str, list[tuple[str, str, str, bool]]] = {
        "Maple & Rye Bakery": [("Jonah Hale", "Owner", "jonah@mapleandrye.example", True)],
        "Harbor Dental": [
            ("Priya Shah", "Office manager", "priya@harbordental.example", True),
            ("Dr. Elena Vos", "Dentist", "elena@harbordental.example", False),
        ],
        "Lumen Studio": [("Avery Chen", "Owner", "avery@lumen.example", True)],
        "Northwind Cafe": [("Sam Ortiz", "Owner", "sam@northwind.example", True)],
        "Oak & Iron Fitness": [
            ("Chris Adler", "General manager", "chris@oakandiron.example", True)
        ],
        "Field & Fern Florist": [("Nina Park", "Owner", "nina@fieldandfern.example", True)],
        "Sable Law": [("Jordan Blake", "Partner", "jordan@sablelaw.example", True)],
        "Kindred Salon": [("Riley Quinn", "Owner", "riley@kindredsalon.example", True)],
        "Redbird Bicycles": [("Morgan Lee", "Shop owner", "morgan@redbird.example", True)],
        "Glasshouse Hotel": [("Helen Cho", "General manager", "helen@glasshouse.example", True)],
        "Pebble Pediatrics": [
            ("Dr. Amir Hassan", "Pediatrician", "amir@pebblepediatrics.example", True)
        ],
        "Marlowe Interiors": [("Claire Marlowe", "Principal", "claire@marlowe.example", True)],
        "Summit Auto": [("Ben Carter", "Owner", "ben@summitauto.example", True)],
        "Hearth & Hide": [("Luis Romero", "Chef-owner", "luis@hearthandhide.example", True)],
        "Atlas Accounting": [("Nora Ellis", "Partner", "nora@atlasaccounting.example", True)],
        "Willow Yoga": [("Sophie Grant", "Founder", "sophie@willowyoga.example", True)],
        "Drift Goods": [("Evan Brooks", "Buyer", "evan@driftgoods.example", True)],
        "Copper Kettle Tea": [("Mia Chen", "Owner", "mia@copperkettle.example", True)],
    }
    session.add_all(
        [
            Contact(
                lead_id=leads[business].id,
                name=name,
                job_title=title,
                email=email,
                is_primary=primary,
            )
            for business, contacts in people.items()
            for name, title, email, primary in contacts
        ]
    )
    session.flush()


def _activities(session: Session, leads: dict[str, Lead], now: datetime) -> None:
    events: list[tuple[str, str, str, str, int]] = [
        ("Maple & Rye Bakery", "lead_created", "Lead created", "Added from a neighborhood map.", 2),
        ("Harbor Dental", "lead_created", "Lead created", "Imported from a maps search.", 6),
        ("Harbor Dental", "status_changed", "Status changed", "NEW to QUALIFIED", 5),
        (
            "Northwind Cafe",
            "lead_created",
            "Lead created",
            "Homepage is hard to read on a phone.",
            3,
        ),
        (
            "Oak & Iron Fitness",
            "audit_completed",
            "Website audit completed",
            "Class schedule is hard to find.",
            8,
        ),
        (
            "Oak & Iron Fitness",
            "status_changed",
            "Status changed",
            "AUDIT_PENDING to AUDIT_COMPLETE",
            8,
        ),
        (
            "Field & Fern Florist",
            "audit_completed",
            "Website audit completed",
            "No website address",
            4,
        ),
        ("Kindred Salon", "status_changed", "Status changed", "MOCKUP_PENDING to MOCKUP_READY", 2),
        ("Redbird Bicycles", "status_changed", "Status changed", "MOCKUP_READY to CONTACTED", 2),
        ("Pebble Pediatrics", "status_changed", "Status changed", "CONTACTED to FOLLOW_UP", 1),
        ("Summit Auto", "status_changed", "Status changed", "FOLLOW_UP to REPLIED", 1),
        ("Hearth & Hide", "status_changed", "Status changed", "REPLIED to MEETING", 1),
        ("Atlas Accounting", "status_changed", "Status changed", "MEETING to PROPOSAL", 2),
        ("Willow Yoga", "status_changed", "Status changed", "PROPOSAL to WON", 3),
        ("Drift Goods", "status_changed", "Status changed", "CONTACTED to LOST", 4),
        ("Copper Kettle Tea", "status_changed", "Status changed", "CONTACTED to NOT_INTERESTED", 6),
    ]
    session.add_all(
        [
            Activity(
                lead_id=leads[business].id,
                type=activity_type,
                title=title,
                description=description,
                created_at=now - timedelta(days=days_ago),
            )
            for business, activity_type, title, description, days_ago in events
        ]
    )


def _audits(session: Session, leads: dict[str, Lead], now: datetime) -> dict[str, WebsiteAudit]:
    weak = _weak_findings()
    audits: dict[str, WebsiteAudit] = {}
    completed = [
        "Oak & Iron Fitness",
        "Sable Law",
        "Kindred Salon",
        "Redbird Bicycles",
        "Glasshouse Hotel",
        "Pebble Pediatrics",
        "Marlowe Interiors",
        "Summit Auto",
        "Hearth & Hide",
        "Atlas Accounting",
        "Willow Yoga",
        "Drift Goods",
    ]
    for name in completed:
        lead = leads[name]
        audit = WebsiteAudit(
            lead_id=lead.id,
            url=lead.website_url,
            status=AuditStatus.COMPLETED.value,
            performance_score=48,
            design_score=40,
            mobile_score=30,
            ux_score=43,
            seo_score=50,
            overall_score=lead.website_quality_score,
            has_ssl=True,
            is_mobile_responsive=False,
            has_clear_cta=False,
            has_contact_form=False,
            has_social_proof=name in {"Willow Yoga", "Atlas Accounting", "Hearth & Hide"},
            has_modern_navigation=name in {"Glasshouse Hotel", "Willow Yoga"},
            issues=[
                {"code": code, "title": title, "detail": detail}
                for code, title, detail, _, _ in weak
            ],
            recommendations=[
                {"code": code, "title": recommendation, "detail": detail}
                for code, _, detail, recommendation, _ in weak
            ],
            raw_analysis={
                "opportunity_score": lead.lead_score,
                "opportunity_breakdown": [
                    {"code": code, "label": title, "points": points}
                    for code, title, _, _, points in weak
                ],
                "title": lead.business_name,
                "final_url": lead.website_url,
                "brand": {
                    "primary_color": "#1F4E3D",
                    "secondary_color": "#1A1A1A",
                    "font_primary": "Georgia",
                    "brand_description": lead.description,
                },
            },
            completed_at=now - timedelta(days=2),
            created_at=now - timedelta(days=3),
        )
        audits[name] = audit

    missing = leads["Field & Fern Florist"]
    audits["Field & Fern Florist"] = WebsiteAudit(
        lead_id=missing.id,
        url=None,
        status=AuditStatus.COMPLETED.value,
        performance_score=0,
        design_score=0,
        mobile_score=0,
        ux_score=0,
        seo_score=0,
        overall_score=0,
        has_ssl=False,
        is_mobile_responsive=False,
        has_clear_cta=False,
        has_contact_form=False,
        has_social_proof=False,
        has_modern_navigation=False,
        issues=[
            {
                "code": "missing_website",
                "title": "Missing website",
                "detail": "This business has no website address.",
            }
        ],
        recommendations=[
            {
                "code": "missing_website",
                "title": "Offer a simple website",
                "detail": "This business has no website address.",
            }
        ],
        raw_analysis={
            "opportunity_score": 30,
            "opportunity_breakdown": [
                {"code": "missing_website", "label": "Missing website", "points": 30}
            ],
            "title": "",
            "final_url": "",
            "brand": {},
        },
        completed_at=now - timedelta(days=4),
        created_at=now - timedelta(days=4),
    )
    session.add_all(audits.values())
    session.flush()
    return audits


def _weak_findings() -> list[tuple[str, str, str, str, int]]:
    return [
        (
            "poor_mobile",
            "Poor mobile UX",
            "The page is wider than a phone screen.",
            "Make the layout fit a phone without horizontal scrolling.",
            20,
        ),
        (
            "outdated_design",
            "Outdated design",
            "The page still uses outdated layout markup.",
            "Replace outdated layout markup with a current page structure.",
            15,
        ),
        (
            "weak_cta",
            "Weak CTA",
            "No clear call to action was found.",
            "Add a clear next step, such as contact, book, or request a quote.",
            10,
        ),
        (
            "no_contact_form",
            "No contact form",
            "No contact form was found on the page.",
            "Add a short contact form.",
            10,
        ),
    ]


def _brands(session: Session, leads: dict[str, Lead]) -> None:
    colors = {
        "Oak & Iron Fitness": ("#1F4E3D", "#F4F1EA", "#C4552A", "Georgia", "Inter"),
        "Kindred Salon": ("#6B3A4A", "#F7F2EF", "#D4A373", "Libre Baskerville", "Inter"),
        "Redbird Bicycles": ("#B42318", "#111827", "#F59E0B", "Inter", "Source Serif 4"),
        "Hearth & Hide": ("#7C2D12", "#FFF7ED", "#1C1917", "Fraunces", "Inter"),
        "Willow Yoga": ("#3F6212", "#F7FEE7", "#0F172A", "Newsreader", "Inter"),
        "Atlas Accounting": ("#1E3A5F", "#F8FAFC", "#0F766E", "Source Serif 4", "Inter"),
    }
    session.add_all(
        [
            BrandProfile(
                lead_id=leads[name].id,
                primary_color=primary,
                secondary_color=secondary,
                accent_color=accent,
                font_primary=font,
                font_secondary=secondary_font,
                brand_description=leads[name].description,
                extracted_content={"headline": leads[name].business_name},
            )
            for name, (primary, secondary, accent, font, secondary_font) in colors.items()
        ]
    )


def _mockups(
    session: Session,
    leads: dict[str, Lead],
    audits: dict[str, WebsiteAudit],
    now: datetime,
) -> None:
    ready = [
        "Kindred Salon",
        "Redbird Bicycles",
        "Pebble Pediatrics",
        "Summit Auto",
        "Hearth & Hide",
        "Atlas Accounting",
        "Willow Yoga",
    ]
    session.add(
        Mockup(
            lead_id=leads["Sable Law"].id,
            audit_id=audits["Sable Law"].id,
            title="Homepage concept",
            status=MockupStatus.GENERATING.value,
            prompt="A calm legal homepage with a clear consult button.",
            provider="sample",
            version=1,
        )
    )
    session.add_all(
        [
            Mockup(
                lead_id=leads[name].id,
                audit_id=audits[name].id,
                title="Homepage concept",
                status=MockupStatus.READY.value,
                prompt=f"A clearer homepage for {name}, with one obvious next step.",
                provider="sample",
                version=1,
                notes="Sample concept for review. No generated image is attached.",
                completed_at=now - timedelta(days=1),
            )
            for name in ready
        ]
    )


def _templates(session: Session) -> dict[str, OutreachTemplate]:
    intro = OutreachTemplate(
        name="Homepage concept",
        channel="email",
        subject="A clearer homepage for {business}",
        body=(
            "Hi {name},\n\n"
            "I put together a homepage concept for {business}. "
            "The current page is hard to use on a phone, and the next step is easy to miss.\n\n"
            "Happy to walk through it if it is useful.\n"
        ),
        template_type="introduction",
        is_active=True,
    )
    follow = OutreachTemplate(
        name="Short follow-up",
        channel="email",
        subject="Re: homepage concept for {business}",
        body="Hi {name},\n\nWanted to make sure the homepage concept landed. Worth a look?\n",
        template_type="follow_up",
        is_active=True,
    )
    session.add_all([intro, follow])
    session.flush()
    return {"intro": intro, "follow": follow}


def _outreach(
    session: Session,
    leads: dict[str, Lead],
    templates: dict[str, OutreachTemplate],
    now: datetime,
) -> None:
    sent = ["Redbird Bicycles", "Glasshouse Hotel", "Pebble Pediatrics", "Marlowe Interiors"]
    session.add_all(
        [
            OutreachMessage(
                lead_id=leads[name].id,
                channel="email",
                subject=f"A clearer homepage for {name}",
                message="Sent the homepage concept and a short note about the mobile layout.",
                template_id=templates["intro"].id,
                status=OutreachStatus.OPENED.value
                if name == "Pebble Pediatrics"
                else OutreachStatus.SENT.value,
                sent_at=now - timedelta(days=3),
                opened_at=(now - timedelta(days=2)) if name == "Pebble Pediatrics" else None,
            )
            for name in sent
        ]
    )
    session.add_all(
        [
            OutreachMessage(
                lead_id=leads["Summit Auto"].id,
                channel="email",
                subject="A clearer homepage for Summit Auto",
                message="Ben replied and asked for a range before a call.",
                template_id=templates["intro"].id,
                status=OutreachStatus.REPLIED.value,
                sent_at=now - timedelta(days=6),
                opened_at=now - timedelta(days=5),
                replied_at=now - timedelta(days=1),
            ),
            OutreachMessage(
                lead_id=leads["Kindred Salon"].id,
                channel="email",
                subject="A clearer homepage for Kindred Salon",
                message="Draft is ready. It still needs a final read before sending.",
                template_id=templates["intro"].id,
                status=OutreachStatus.DRAFT.value,
            ),
            OutreachMessage(
                lead_id=leads["Willow Yoga"].id,
                channel="email",
                subject="A clearer homepage for Willow Yoga",
                message="Sophie replied and booked a kickoff.",
                template_id=templates["intro"].id,
                status=OutreachStatus.REPLIED.value,
                sent_at=now - timedelta(days=12),
                opened_at=now - timedelta(days=11),
                replied_at=now - timedelta(days=8),
            ),
        ]
    )


def _followups(session: Session, leads: dict[str, Lead], now: datetime) -> None:
    session.add_all(
        [
            Followup(
                lead_id=leads["Pebble Pediatrics"].id,
                scheduled_for=now - timedelta(days=1),
                type="email",
                status=FollowupStatus.DUE.value,
                notes="They opened the first note. Ask if the homepage concept was useful.",
            ),
            Followup(
                lead_id=leads["Marlowe Interiors"].id,
                scheduled_for=now + timedelta(hours=4),
                type="email",
                status=FollowupStatus.SCHEDULED.value,
                notes="Send the short follow-up this afternoon.",
            ),
            Followup(
                lead_id=leads["Redbird Bicycles"].id,
                scheduled_for=now + timedelta(days=3),
                type="email",
                status=FollowupStatus.SCHEDULED.value,
                notes="Check whether Morgan had a chance to look.",
            ),
            Followup(
                lead_id=leads["Glasshouse Hotel"].id,
                scheduled_for=now + timedelta(days=6),
                type="call",
                status=FollowupStatus.SCHEDULED.value,
                notes="Helen asked for a call next week.",
            ),
            Followup(
                lead_id=leads["Willow Yoga"].id,
                scheduled_for=now - timedelta(days=8),
                type="email",
                status=FollowupStatus.COMPLETED.value,
                notes="Follow-up turned into a kickoff booking.",
                completed_at=now - timedelta(days=8),
            ),
        ]
    )


if __name__ == "__main__":
    created = seed()
    if created:
        print(f"Seeded {created} sample leads.")
    else:
        print("Leads already exist. Sample data was left unchanged.")

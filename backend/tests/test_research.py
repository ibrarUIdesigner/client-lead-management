from sqlalchemy import select

from app.core.config import Settings
from app.db.session import create_db_engine, create_session_factory
from app.models.enums import LeadStatus, ResearchStatus
from app.models.lead import Lead
from app.models.lead_research import LeadResearch
from app.services.research import ResearchService


def _test_settings() -> Settings:
    neon_url = (
        "postgresql+psycopg://neondb_owner:npg_bX0lSkEyeJV9@"
        "ep-sparkling-credit-b2x3eogx-pooler.c-6.eu-central-1.aws.neon.tech/neondb?sslmode=require"
    )
    return Settings(
        app_env="test",
        database_url=neon_url,
        postgres_url=neon_url,
        cors_origins="http://localhost:5175",
        tavily_api_key="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",
        exa_api_key="2a1457b0-48ce-4176-90e6-f7cf480c0183",
        gemini_api_key="mock",
    )


def test_research_service_heuristic_synthesis() -> None:
    settings = _test_settings()
    engine = create_db_engine(settings.database_url)
    session_factory = create_session_factory(engine)

    with session_factory() as session:
        lead = Lead(
            business_name="Atlas Dental Studio",
            industry="Healthcare & Dental",
            city="Denver",
            country="USA",
            website_url="https://atlasdental.example.com",
            email="info@atlasdental.example.com",
            lead_status=LeadStatus.NEW.value,
        )
        session.add(lead)
        session.flush()

        service = ResearchService(session, settings)
        mock_sources = [
            {
                "title": "Atlas Dental Reviews",
                "url": "https://example.com/reviews",
                "snippet": "Patients love the dentists but complain about phone wait times.",
                "provider": "tavily",
            },
            {
                "title": "Atlas Dental Practice News",
                "url": "https://example.com/news",
                "snippet": "Leading cosmetic and restorative dentistry in Denver.",
                "provider": "exa",
            },
        ]

        structured, summary = service._heuristic_synthesis(lead, mock_sources, "Atlas Dental")
        assert "SECTION 1: COMPREHENSIVE RESEARCH" in summary
        assert "SECTION 2: EXECUTIVE SUMMARY & PROACTIVE SOLUTIONS" in summary
        assert len(structured["proactive_solutions"]) > 0

        research = LeadResearch(
            lead_id=lead.id,
            status=ResearchStatus.COMPLETED.value,
            summary=summary,
            research_data=structured,
            sources=mock_sources,
        )
        session.add(research)
        session.flush()

        saved = service.get_for_lead(lead.id)
        assert saved is not None
        assert saved.status == ResearchStatus.COMPLETED.value
        assert len(saved.sources) == 2

        session.delete(lead)
        session.flush()

        remaining_research = session.scalar(
            select(LeadResearch).where(LeadResearch.lead_id == lead.id)
        )
        assert remaining_research is None
        session.rollback()


def test_research_sequential_fallback_logic(monkeypatch) -> None:
    settings = _test_settings()
    engine = create_db_engine(settings.database_url)
    session_factory = create_session_factory(engine)

    with session_factory() as session:
        service = ResearchService(session, settings)

        # 1. Primary Tavily succeeds: Exa must NOT be called
        exa_called = False

        def mock_tavily_success(query, lead=None):
            return {
                "results": [
                    {"title": "Tavily Hit", "url": "https://example.com", "content": "Hit"}
                ]
            }

        def mock_exa_spy(query, lead=None):
            nonlocal exa_called
            exa_called = True
            return {
                "results": [
                    {"title": "Exa Hit", "url": "https://example.com/exa", "highlights": ["Hit"]}
                ]
            }

        monkeypatch.setattr(service, "_search_tavily", mock_tavily_success)
        monkeypatch.setattr(service, "_search_exa", mock_exa_spy)

        sources, provider, fallback_used, fallback_reason, _, _ = service._fetch_sources_sequential(
            "test query", preferred_tool="tavily"
        )
        assert provider == "tavily"
        assert fallback_used is False
        assert fallback_reason is None
        assert exa_called is False
        assert len(sources) == 1
        assert sources[0]["provider"] == "tavily"

        # 2. Primary Tavily fails / hits limit: Fallback to Exa must be triggered
        def mock_tavily_rate_limit(query, lead=None):
            return {"error": "429 Rate limit reached for this month", "results": []}

        monkeypatch.setattr(service, "_search_tavily", mock_tavily_rate_limit)

        res = service._fetch_sources_sequential(
            "test query", preferred_tool="tavily"
        )
        sources2, provider2, fallback_used2, fallback_reason2, _, _ = res
        assert provider2 == "exa"
        assert fallback_used2 is True
        assert "429 Rate limit" in (fallback_reason2 or "")
        assert exa_called is True
        assert len(sources2) == 1
        assert sources2[0]["provider"] == "exa"

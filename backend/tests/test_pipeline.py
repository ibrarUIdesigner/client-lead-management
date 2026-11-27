from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.config import Settings, get_settings
from app.db.session import create_db_engine
from app.models.enums import LeadStatus, PipelineJobStatus, PipelineStep
from app.models.lead import Lead
from app.models.pipeline_job import PipelineJob
from app.services.pipeline import PipelineService


def _settings(**overrides: object) -> Settings:
    values: dict[str, object] = {
        "app_env": "test",
        "database_url": "postgresql+psycopg://app:app@127.0.0.1:1/x",
        "postgres_url": "",
        "pipeline_min_score": 40,
        "tavily_api_key": "",
        "exa_api_key": "",
        "gemini_api_key": "",
        "groq_api_key": "",
    }
    values.update(overrides)
    return Settings(**values)  # type: ignore[arg-type]


def _lead(**overrides: object) -> Lead:
    values: dict[str, object] = {
        "business_name": "Acme Plumbing",
        "lead_status": LeadStatus.NEW.value,
        "lead_score": 80,
        "email": "hello@acme.example",
        "website_url": None,
        "do_not_contact": False,
        "email_suppressed": False,
        "pipeline_paused": False,
    }
    values.update(overrides)
    return Lead(**values)  # type: ignore[arg-type]


def _job(step: str, status: str, attempts: int = 1) -> PipelineJob:
    return PipelineJob(step=step, status=status, attempts=attempts, max_attempts=3)


@pytest.fixture
def service(monkeypatch: pytest.MonkeyPatch) -> PipelineService:
    svc = PipelineService(session=None, settings=_settings())  # type: ignore[arg-type]
    monkeypatch.setattr(svc, "_has_ready_mockup", lambda _id: False)
    monkeypatch.setattr(svc, "_has_outreach", lambda _id: False)
    return svc


def test_new_scored_lead_starts_with_audit(service: PipelineService) -> None:
    assert service.decide_next_step(_lead(), []) == "audit"


def test_lead_with_website_and_no_email_is_enriched_first(service: PipelineService) -> None:
    lead = _lead(email=None, website_url="https://acme.example")
    assert service.decide_next_step(lead, []) == "enrich"


def test_steps_run_in_order_and_never_repeat(service: PipelineService) -> None:
    lead = _lead()
    done = [_job("audit", "DONE")]
    assert service.decide_next_step(lead, done) == "mockup"
    done.append(_job("mockup", "SKIPPED"))
    assert service.decide_next_step(lead, done) == "draft"
    done.append(_job("draft", "DONE"))
    assert service.decide_next_step(lead, done) is None


def test_research_only_runs_when_a_provider_is_configured(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    svc = PipelineService(session=None, settings=_settings(tavily_api_key="x"))  # type: ignore[arg-type]
    monkeypatch.setattr(svc, "_has_ready_mockup", lambda _id: False)
    monkeypatch.setattr(svc, "_has_outreach", lambda _id: False)
    assert svc.decide_next_step(_lead(), [_job("audit", "DONE")]) == "research"


def test_open_job_blocks_planning(service: PipelineService) -> None:
    assert service.decide_next_step(_lead(), [_job("audit", "QUEUED")]) is None
    assert service.decide_next_step(_lead(), [_job("audit", "RUNNING")]) is None


def test_failed_step_is_only_final_after_all_attempts(service: PipelineService) -> None:
    lead = _lead()
    assert service.decide_next_step(lead, [_job("audit", "FAILED", attempts=1)]) == "audit"
    assert service.decide_next_step(lead, [_job("audit", "FAILED", attempts=3)]) == "mockup"


@pytest.mark.parametrize(
    "overrides",
    [
        {"pipeline_paused": True},
        {"do_not_contact": True},
        {"lead_status": LeadStatus.CONTACTED.value},
        {"lead_status": LeadStatus.REPLIED.value},
        {"lead_score": 10},
        {"lead_score": None},
    ],
)
def test_ineligible_leads_are_ignored(
    service: PipelineService, overrides: dict[str, object]
) -> None:
    assert service.decide_next_step(_lead(**overrides), []) is None


def test_lead_without_email_never_gets_a_draft(service: PipelineService) -> None:
    lead = _lead(email=None)
    jobs = [_job("audit", "DONE"), _job("mockup", "DONE")]
    assert service.decide_next_step(lead, jobs) is None


def test_budgets_are_defined_for_heavy_steps(service: PipelineService) -> None:
    assert service.budget(PipelineStep.AUDIT.value) == 25
    assert service.budget(PipelineStep.MOCKUP.value) == 10
    assert service.budget(PipelineStep.ENRICH.value) is None


@pytest.fixture
def db_session():
    settings = get_settings()
    engine = create_db_engine(settings.database_url)
    connection = engine.connect()
    transaction = connection.begin()
    session = Session(bind=connection, join_transaction_mode="create_savepoint")
    try:
        yield session
    finally:
        session.close()
        transaction.rollback()
        connection.close()
        engine.dispose()


def test_worker_walks_a_no_website_lead_through_the_pipeline(db_session: Session) -> None:
    lead = _lead(business_name="Northwind Plumbing", source_key="test:pipeline:1")
    db_session.add(lead)
    db_session.flush()
    service = PipelineService(db_session, _settings())

    job = service.enqueue_next(lead)
    assert job is not None and job.step == "audit"
    assert lead.lead_status == LeadStatus.QUALIFIED.value

    outcomes: list[tuple[str, str]] = []
    for _ in range(6):
        claimed = service.claim_next()
        if claimed is None:
            break
        step = claimed.step
        outcomes.append((step, service.run_job(claimed.id)))

    # No website: the audit records that. No AI keys: mockup and draft are skipped.
    assert [step for step, _ in outcomes] == ["audit", "mockup", "draft"]
    assert outcomes[0][1] == PipelineJobStatus.DONE.value
    assert all(result == PipelineJobStatus.SKIPPED.value for _, result in outcomes[1:])
    assert service.enqueue_next(lead) is None


def test_second_open_job_for_same_step_is_rejected(db_session: Session) -> None:
    lead = _lead(source_key="test:pipeline:2")
    db_session.add(lead)
    db_session.flush()
    db_session.add(PipelineJob(lead_id=lead.id, step="audit", status="QUEUED"))
    db_session.flush()
    with pytest.raises(IntegrityError):
        with db_session.begin_nested():
            db_session.add(PipelineJob(lead_id=lead.id, step="audit", status="QUEUED"))
            db_session.flush()


def test_budget_blocks_claiming(db_session: Session) -> None:
    settings = _settings(pipeline_daily_audits=1)
    lead_a = _lead(business_name="A", source_key="test:pipeline:3")
    lead_b = _lead(business_name="B", source_key="test:pipeline:4")
    db_session.add_all([lead_a, lead_b])
    db_session.flush()
    now = datetime.now(UTC)
    db_session.add(
        PipelineJob(
            lead_id=lead_a.id,
            step="audit",
            status="DONE",
            attempts=1,
            started_at=now,
            finished_at=now,
        )
    )
    db_session.add(PipelineJob(lead_id=lead_b.id, step="audit", status="QUEUED"))
    db_session.flush()
    service = PipelineService(db_session, settings)
    assert service.claim_next() is None
    queued = db_session.scalar(select(PipelineJob).where(PipelineJob.lead_id == lead_b.id))
    assert queued is not None and queued.status == "QUEUED"


def test_stale_running_jobs_are_recovered(db_session: Session) -> None:
    lead = _lead(source_key="test:pipeline:5")
    db_session.add(lead)
    db_session.flush()
    old = datetime.now(UTC) - timedelta(minutes=30)
    job = PipelineJob(lead_id=lead.id, step="audit", status="RUNNING", attempts=1, started_at=old)
    db_session.add(job)
    db_session.flush()
    assert PipelineService(db_session, _settings()).recover_stale() == 1
    assert job.status == "QUEUED"

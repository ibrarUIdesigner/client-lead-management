"""Automation pipeline: enrich -> audit -> research -> mockup -> draft.

Each step is a row in ``pipeline_jobs``. A tick (called by cron) claims due jobs,
runs them, and queues the next step for the lead. Nothing here sends email: the last
step only creates a DRAFT that waits for your approval.

Rules that keep the pipeline safe and cheap:
- One open job per lead and step (database unique index).
- A step that finished, was skipped, or used up its retries is never repeated
  automatically. Use retry to run it again.
- Heavy steps have daily budgets so free API tiers are not exhausted.
- Leads that are paused, marked do-not-contact, or already contacted are ignored.
"""

from __future__ import annotations

import asyncio
import logging
import time
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import UUID

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import Settings
from app.core.errors import AppError
from app.models.enums import (
    AuditStatus,
    FollowupStatus,
    LeadStatus,
    MockupStatus,
    NotificationPriority,
    NotificationType,
    PipelineJobStatus,
    PipelineStep,
    ResearchStatus,
)
from app.models.followup import Followup
from app.models.lead import Lead
from app.models.mockup import Mockup
from app.models.outreach import OutreachMessage
from app.models.pipeline_job import PipelineJob
from app.models.website_audit import WebsiteAudit
from app.repositories.activities import ActivityRepository

logger = logging.getLogger(__name__)

ACTIVE_STATUSES = {
    LeadStatus.NEW.value,
    LeadStatus.QUALIFIED.value,
    LeadStatus.AUDIT_PENDING.value,
    LeadStatus.AUDIT_COMPLETE.value,
    LeadStatus.MOCKUP_PENDING.value,
    LeadStatus.MOCKUP_READY.value,
}
HEAVY_STEPS = {PipelineStep.AUDIT.value, PipelineStep.MOCKUP.value}
HIGH_OPPORTUNITY_SCORE = 70
STALE_AFTER = timedelta(minutes=10)
RECHECK_AFTER = timedelta(hours=6)
SWEEP_LEAD_LIMIT = 100
SWEEP_ENQUEUE_LIMIT = 20
_FINISHED = (PipelineJobStatus.DONE.value, PipelineJobStatus.SKIPPED.value)
_OPEN = (PipelineJobStatus.QUEUED.value, PipelineJobStatus.RUNNING.value)


class RetryLater(Exception):
    """Raised by a step that should be tried again later without counting as broken."""

    def __init__(self, message: str, minutes: int = 5) -> None:
        super().__init__(message)
        self.minutes = minutes


@dataclass
class TickSummary:
    followups_due: int = 0
    leads_examined: int = 0
    jobs_queued: int = 0
    jobs_run: int = 0
    jobs_done: int = 0
    jobs_skipped: int = 0
    jobs_failed: int = 0
    stale_recovered: int = 0
    followups_sent: int = 0
    followups_waiting: int = 0
    discovery: dict[str, Any] = field(default_factory=dict)
    report: str = ""
    learning: str = ""
    stopped_because: str = "queue empty"
    steps: list[str] = field(default_factory=list)

    def as_dict(self) -> dict[str, Any]:
        return dict(self.__dict__)


def _now() -> datetime:
    return datetime.now(UTC)


def _day_start() -> datetime:
    return _now().replace(hour=0, minute=0, second=0, microsecond=0)


class PipelineService:
    def __init__(self, session: Session, settings: Settings) -> None:
        self.session = session
        self.settings = settings
        self._exclusion_cache: Any = None
        self.activities = ActivityRepository(session)

    # ------------------------------------------------------------------ queries

    def jobs_for_lead(self, lead_id: UUID) -> list[PipelineJob]:
        return list(
            self.session.scalars(
                select(PipelineJob)
                .where(PipelineJob.lead_id == lead_id)
                .order_by(PipelineJob.created_at.asc())
            )
        )

    def budget(self, step: str) -> int | None:
        return {
            PipelineStep.AUDIT.value: self.settings.pipeline_daily_audits,
            PipelineStep.RESEARCH.value: self.settings.pipeline_daily_research,
            PipelineStep.MOCKUP.value: self.settings.pipeline_daily_mockups,
            PipelineStep.DRAFT.value: self.settings.pipeline_daily_drafts,
        }.get(step)

    def used_today(self, step: str) -> int:
        count = self.session.scalar(
            select(func.count())
            .select_from(PipelineJob)
            .where(
                PipelineJob.step == step,
                PipelineJob.started_at >= _day_start(),
                PipelineJob.status.in_(
                    [
                        PipelineJobStatus.RUNNING.value,
                        PipelineJobStatus.DONE.value,
                        PipelineJobStatus.FAILED.value,
                    ]
                ),
            )
        )
        return int(count or 0)

    def has_budget(self, step: str) -> bool:
        limit = self.budget(step)
        return limit is None or self.used_today(step) < limit

    def status_overview(self) -> dict[str, Any]:
        rows = self.session.execute(
            select(PipelineJob.status, func.count()).group_by(PipelineJob.status)
        ).all()
        return {
            "enabled": self.settings.pipeline_enabled,
            "min_score": self.settings.pipeline_min_score,
            "jobs": {status: int(count) for status, count in rows},
            "budgets": {
                step.value: {"used": self.used_today(step.value), "limit": self.budget(step.value)}
                for step in PipelineStep
                if self.budget(step.value) is not None
            },
        }

    # ----------------------------------------------------------------- planning

    def decide_next_step(self, lead: Lead, jobs: list[PipelineJob] | None = None) -> str | None:
        """Decide from stored facts. Returns the next step name or None."""
        if lead.pipeline_paused or lead.do_not_contact:
            return None
        if lead.lead_status not in ACTIVE_STATUSES:
            return None
        if (lead.lead_score or 0) < self.settings.pipeline_min_score:
            return None
        if self._excluded(lead):
            return None
        jobs = jobs if jobs is not None else self.jobs_for_lead(lead.id)
        if any(j.status in _OPEN for j in jobs):
            return None
        attempted = {
            j.step
            for j in jobs
            if j.status in _FINISHED
            or (j.status == PipelineJobStatus.FAILED.value and j.attempts >= j.max_attempts)
        }
        has_site = bool((lead.website_url or "").strip())
        has_email = bool((lead.email or "").strip())

        if PipelineStep.ENRICH.value not in attempted and not has_email and has_site:
            return PipelineStep.ENRICH.value
        if PipelineStep.AUDIT.value not in attempted:
            return PipelineStep.AUDIT.value
        if (
            PipelineStep.RESEARCH.value not in attempted
            and self.settings.lead_research_configured
        ):
            return PipelineStep.RESEARCH.value
        if PipelineStep.MOCKUP.value not in attempted and not self._has_ready_mockup(lead.id):
            return PipelineStep.MOCKUP.value
        if (
            PipelineStep.DRAFT.value not in attempted
            and has_email
            and not lead.email_suppressed
            and not self._has_outreach(lead.id)
        ):
            return PipelineStep.DRAFT.value
        if (
            PipelineStep.SEND.value not in attempted
            and has_email
            and self._auto_send_enabled()
            and self._has_unsent_draft(lead.id)
        ):
            return PipelineStep.SEND.value
        return None

    def enqueue_next(self, lead: Lead) -> PipelineJob | None:
        if lead.lead_score is None and lead.lead_status in ACTIVE_STATUSES:
            self._refresh_score(lead)
        step = self.decide_next_step(lead)
        lead.pipeline_checked_at = _now()
        if step is None:
            return None
        self._qualify(lead)
        job = PipelineJob(lead_id=lead.id, step=step, status=PipelineJobStatus.QUEUED.value)
        self.session.add(job)
        self.session.flush()
        return job

    def sweep_leads(self) -> tuple[int, int]:
        cutoff = _now() - RECHECK_AFTER
        leads = list(
            self.session.scalars(
                select(Lead)
                .where(
                    Lead.lead_status.in_(ACTIVE_STATUSES),
                    Lead.pipeline_paused.is_(False),
                    Lead.do_not_contact.is_(False),
                    or_(
                        Lead.lead_score.is_(None),
                        Lead.lead_score >= self.settings.pipeline_min_score,
                    ),
                    or_(Lead.pipeline_checked_at.is_(None), Lead.pipeline_checked_at < cutoff),
                )
                .order_by(Lead.lead_score.desc(), Lead.created_at.asc())
                .limit(SWEEP_LEAD_LIMIT)
            )
        )
        queued = 0
        examined = 0
        for lead in leads:
            if queued >= SWEEP_ENQUEUE_LIMIT:
                break
            examined += 1
            try:
                with self.session.begin_nested():
                    if self.enqueue_next(lead) is not None:
                        queued += 1
            except Exception:
                logger.exception("pipeline_enqueue_failed lead_id=%s", lead.id)
        return examined, queued

    def sweep_followups(self) -> int:
        rows = list(
            self.session.scalars(
                select(Followup).where(
                    Followup.status == FollowupStatus.SCHEDULED.value,
                    Followup.scheduled_for <= _now(),
                )
            )
        )
        for row in rows:
            row.status = FollowupStatus.DUE.value
            lead = self.session.get(Lead, row.lead_id)
            if lead is None or lead.do_not_contact:
                continue
            self._notify(
                lead,
                NotificationType.FOLLOWUP_DUE,
                "Follow-up due",
                f"A follow-up for {lead.business_name} is due.",
                NotificationPriority.HIGH,
                dedup_key=f"followup-due:{row.id}",
            )
        return len(rows)

    def recover_stale(self) -> int:
        rows = list(
            self.session.scalars(
                select(PipelineJob).where(
                    PipelineJob.status == PipelineJobStatus.RUNNING.value,
                    PipelineJob.started_at < _now() - STALE_AFTER,
                )
            )
        )
        for job in rows:
            job.last_error = "Worker stopped before this step finished."
            self._schedule_retry_or_fail(job)
        return len(rows)

    # ---------------------------------------------------------------- execution

    def claim_next(self, *, allow_heavy: bool = True) -> PipelineJob | None:
        candidates = list(
            self.session.scalars(
                select(PipelineJob)
                .where(
                    PipelineJob.status == PipelineJobStatus.QUEUED.value,
                    PipelineJob.run_after <= _now(),
                    PipelineJob.step != PipelineStep.DRAFT.value,
                )
                .order_by(PipelineJob.run_after.asc())
                .with_for_update(skip_locked=True)
                .limit(10)
            )
        )
        for job in candidates:
            if job.step in HEAVY_STEPS and not allow_heavy:
                continue
            if not self.has_budget(job.step):
                continue
            return self._start(job)
        draft = self._next_draft_job()
        if draft is not None:
            return self._start(draft)
        self.session.commit()  # nothing changed; releases the row locks
        return None

    def _start(self, job: PipelineJob) -> PipelineJob:
        job.status = PipelineJobStatus.RUNNING.value
        job.attempts += 1
        job.started_at = _now()
        self.session.commit()
        return job

    # --------------------------------------------------------------- draft slots

    def draft_slots_left(self) -> int:
        """How many more leads may get a draft today (your daily outreach limit)."""
        from app.services.automation_config import get_config

        limit = get_config(self.session).outreach_daily_limit
        return max(0, limit - self.used_today(PipelineStep.DRAFT.value))

    def queued_draft_ranking(self) -> list[tuple[PipelineJob, Any]]:
        """Queued draft jobs, best lead first."""
        from app.services.outreach_priority import rank_leads

        jobs = list(
            self.session.scalars(
                select(PipelineJob).where(
                    PipelineJob.step == PipelineStep.DRAFT.value,
                    PipelineJob.status == PipelineJobStatus.QUEUED.value,
                    PipelineJob.run_after <= _now(),
                )
            )
        )
        ranks = rank_leads(self.session, self.settings, [j.lead_id for j in jobs])
        ranked = [(j, ranks[j.lead_id]) for j in jobs if j.lead_id in ranks]
        ranked.sort(key=lambda pair: pair[1].score, reverse=True)
        return ranked

    def _next_draft_job(self) -> PipelineJob | None:
        """The best waiting lead, if a daily slot is free. Others wait for tomorrow."""
        if not self.has_budget(PipelineStep.DRAFT.value) or self.draft_slots_left() <= 0:
            return None
        for job, priority in self.queued_draft_ranking():
            locked = self.session.scalar(
                select(PipelineJob)
                .where(PipelineJob.id == job.id, PipelineJob.status == PipelineJobStatus.QUEUED.value)
                .with_for_update(skip_locked=True)
            )
            if locked is None:
                continue
            if priority.blocked:
                locked.status = PipelineJobStatus.SKIPPED.value
                locked.finished_at = _now()
                locked.result = {"detail": "Your country policy blocks email to this lead."}
                continue
            return locked
        return None

    def run_job(self, job_id: UUID) -> str:
        job = self.session.get(PipelineJob, job_id)
        if job is None or job.status != PipelineJobStatus.RUNNING.value:
            return "ignored"
        lead_id = job.lead_id
        step = job.step
        handlers = {
            PipelineStep.ENRICH.value: self._step_enrich,
            PipelineStep.AUDIT.value: self._step_audit,
            PipelineStep.RESEARCH.value: self._step_research,
            PipelineStep.MOCKUP.value: self._step_mockup,
            PipelineStep.DRAFT.value: self._step_draft,
            PipelineStep.SEND.value: self._step_send,
        }
        try:
            lead = self.session.get(Lead, lead_id)
            if lead is None:
                raise AppError(code="LEAD_NOT_FOUND", message="Lead was removed.", status_code=404)
            outcome, detail = handlers[step](lead)
            job = self._reload(job_id)
            job.status = outcome
            job.finished_at = _now()
            job.last_error = None
            job.result = {"detail": detail}
            self.session.commit()
            result = outcome
        except RetryLater as exc:
            self.session.rollback()
            job = self._reload(job_id)
            job.status = PipelineJobStatus.QUEUED.value
            job.attempts = max(0, job.attempts - 1)
            job.run_after = _now() + timedelta(minutes=exc.minutes)
            job.last_error = str(exc)[:500]
            self.session.commit()
            return "retry"
        except Exception as exc:
            self.session.rollback()
            logger.exception("pipeline_step_failed step=%s lead_id=%s", step, lead_id)
            job = self._reload(job_id)
            job.last_error = (getattr(exc, "message", None) or str(exc) or type(exc).__name__)[:500]
            self._schedule_retry_or_fail(job)
            self.session.commit()
            result = job.status
        lead = self.session.get(Lead, lead_id)
        if lead is not None:
            try:
                self.enqueue_next(lead)
                self.session.commit()
            except Exception:
                self.session.rollback()
                logger.exception("pipeline_enqueue_after_run_failed lead_id=%s", lead_id)
        return result

    def retry_job(self, job_id: UUID) -> PipelineJob:
        job = self.session.get(PipelineJob, job_id)
        if job is None:
            raise AppError(code="NOT_FOUND", message="Job not found.", status_code=404)
        if job.status in _OPEN:
            return job
        job.status = PipelineJobStatus.QUEUED.value
        job.attempts = 0
        job.run_after = _now()
        job.last_error = None
        job.finished_at = None
        try:
            self.session.flush()
        except Exception as exc:  # another open job for this step already exists
            self.session.rollback()
            raise AppError(
                code="JOB_ALREADY_OPEN",
                message="That step is already queued for this lead.",
                status_code=409,
            ) from exc
        return job

    def _reload(self, job_id: UUID) -> PipelineJob:
        job = self.session.get(PipelineJob, job_id)
        if job is None:
            raise AppError(code="NOT_FOUND", message="Job not found.", status_code=404)
        return job

    def _schedule_retry_or_fail(self, job: PipelineJob) -> None:
        if job.attempts < job.max_attempts:
            job.status = PipelineJobStatus.QUEUED.value
            job.run_after = _now() + timedelta(minutes=15 * max(1, job.attempts))
        else:
            job.status = PipelineJobStatus.FAILED.value
            job.finished_at = _now()

    # -------------------------------------------------------------------- steps

    def _step_enrich(self, lead: Lead) -> tuple[str, str]:
        from app.services.email_finder import find_business_email

        if (lead.email or "").strip():
            return PipelineJobStatus.SKIPPED.value, "Lead already has an email."
        if not (lead.website_url or "").strip():
            return PipelineJobStatus.SKIPPED.value, "No website to search."
        email = find_business_email(lead.website_url, settings=self.settings)
        if not email:
            return PipelineJobStatus.DONE.value, "No public email found."
        lead.email = email
        lead.tags = [t for t in (lead.tags or []) if t != "needs-contact"]
        self.activities.add(
            lead.id, "email_found", "Contact email found", description="Found on the business website."
        )
        self.session.flush()
        return PipelineJobStatus.DONE.value, "Email found."

    def _step_audit(self, lead: Lead) -> tuple[str, str]:
        from app.services.audits import AuditService

        service = AuditService(
            self.session,
            self.settings.storage_dir,
            self.settings.google_pagespeed_api_key,
            self.settings.discovery_user_agent,
        )
        try:
            audit, should_run = service.prepare(lead.id)
        except AppError as exc:
            if exc.code == "AUDIT_IN_PROGRESS":
                raise RetryLater("An audit is already running.") from exc
            return PipelineJobStatus.SKIPPED.value, exc.message
        self.session.commit()
        if should_run:
            asyncio.run(service.execute(audit.id))
            self.session.commit()
            self.session.refresh(audit)
            if audit.status == AuditStatus.FAILED.value:
                raise RuntimeError("The website audit failed.")
        self._refresh_score(lead)
        return PipelineJobStatus.DONE.value, f"Audit {audit.status.lower()}."

    def _step_research(self, lead: Lead) -> tuple[str, str]:
        from app.services.research import ResearchService

        if not self.settings.lead_research_configured:
            return PipelineJobStatus.SKIPPED.value, "No research provider configured."
        service = ResearchService(self.session, self.settings)
        research, should_run = service.prepare_research(lead.id)
        if should_run:
            service.execute_research(research.id)
            self.session.commit()
        self.session.refresh(research)
        if research.status == ResearchStatus.FAILED.value:
            raise RuntimeError(research.error_message or "Research failed.")
        self._refresh_score(lead)
        return PipelineJobStatus.DONE.value, "Research complete."

    def _step_mockup(self, lead: Lead) -> tuple[str, str]:
        from app.schemas.design_guides import MockupCreate
        from app.services.mockup_eligibility import evaluate_mockup_eligibility
        from app.services.mockups import MockupService
        from app.services.outreach_ai import provider_ready

        if self._has_ready_mockup(lead.id):
            return PipelineJobStatus.SKIPPED.value, "A mockup already exists."
        eligibility = evaluate_mockup_eligibility(lead, self._latest_completed_audit(lead.id))
        if not eligibility.allowed:
            return PipelineJobStatus.SKIPPED.value, eligibility.message
        provider = next(
            (name for name in ("gemini", "groq") if provider_ready(self.settings, name)), None
        )
        if provider is None:
            return PipelineJobStatus.SKIPPED.value, "No AI provider is configured for mockups."
        service = MockupService(self.session, self.settings)
        created = service.create(MockupCreate(lead_id=lead.id, provider=provider))
        self.session.commit()
        asyncio.run(service.execute(created.id))
        self.session.commit()
        mockup = self.session.get(Mockup, created.id)
        if mockup is None or mockup.status != MockupStatus.READY.value:
            raise RuntimeError(f"Mockup ended as {mockup.status if mockup else 'missing'}.")
        self._notify(
            lead,
            NotificationType.MOCKUP_READY,
            "Mockup ready",
            f"A homepage concept for {lead.business_name} is ready.",
            NotificationPriority.NORMAL,
            dedup_key=f"mockup-ready:{mockup.id}",
        )
        return PipelineJobStatus.DONE.value, "Mockup ready."

    def _step_draft(self, lead: Lead) -> tuple[str, str]:
        from app.schemas.outreach import OutreachGenerate
        from app.services.outreach import OutreachService
        from app.services.outreach_ai import resolve_email_provider

        if not (lead.email or "").strip() or lead.do_not_contact or lead.email_suppressed:
            return PipelineJobStatus.SKIPPED.value, "Lead cannot be emailed."
        if self._has_outreach(lead.id):
            return PipelineJobStatus.SKIPPED.value, "A draft already exists."
        if resolve_email_provider(self.settings) is None:
            return PipelineJobStatus.SKIPPED.value, "No AI provider is configured for drafts."
        from app.models.outreach import OutreachMessage as MessageRow
        from app.services.automation import recent_outreach_bodies
        from app.services.draft_similarity import SIMILAR_AT, most_similar
        from app.services.outreach_variants import pick_variant

        from app.services.learning import load_state

        learning = load_state(self.session)
        service = OutreachService(self.session)
        tone, style = pick_variant(lead.id, learning=learning)
        message = service.generate(lead.id, OutreachGenerate(use_ai=True, tone=tone, style=style))
        recent = recent_outreach_bodies(self.session, exclude_id=message.id)
        row = self.session.get(MessageRow, message.id)
        if row is not None and recent and most_similar(row.message or "", recent) >= SIMILAR_AT:
            # Reads like a recent email: write it once more in a different voice.
            self.session.delete(row)
            self.session.commit()
            tone, style = pick_variant(lead.id, shift=1, learning=learning)
            message = service.generate(
                lead.id, OutreachGenerate(use_ai=True, tone=tone, style=style)
            )
        self._notify(
            lead,
            NotificationType.EMAIL_DRAFT_READY,
            "Draft ready for review",
            f"Review and approve the email to {lead.business_name}. Nothing has been sent.",
            NotificationPriority.NORMAL,
            dedup_key=f"draft-ready:{message.id}",
        )
        return PipelineJobStatus.DONE.value, "Draft created. Waiting for your approval."

    def _step_send(self, lead: Lead) -> tuple[str, str]:
        from app.models.enums import OutreachStatus
        from app.schemas.gmail import LeadEmailSendRequest
        from app.services.automation import (
            check_draft_quality,
            in_send_window,
            schedule_followup_sequence,
        )
        from app.services.gmail_mail import GmailMailService
        from app.services.outreach_policy import can_auto_send, sent_today

        if not self._auto_send_enabled():
            raise RetryLater("Automatic sending is switched off.", minutes=60)
        message = self.session.scalar(
            select(OutreachMessage)
            .where(
                OutreachMessage.lead_id == lead.id,
                OutreachMessage.status.in_([OutreachStatus.DRAFT.value, OutreachStatus.READY.value]),
            )
            .order_by(OutreachMessage.created_at.desc())
            .limit(1)
        )
        if message is None:
            return PipelineJobStatus.SKIPPED.value, "No unsent draft."
        allowed, reason = can_auto_send(lead, self.settings)
        if not allowed:
            return PipelineJobStatus.SKIPPED.value, f"Left for you to send manually: {reason}"
        from app.services.automation import recent_outreach_bodies

        problems = check_draft_quality(
            message.subject,
            message.message,
            lead.business_name,
            recent_bodies=recent_outreach_bodies(self.session, exclude_id=message.id),
        )
        if problems:
            self._notify(
                lead,
                NotificationType.EMAIL_DRAFT_READY,
                "Draft needs your review",
                f"The draft for {lead.business_name} was not sent: {', '.join(problems)}.",
                NotificationPriority.HIGH,
                dedup_key=f"draft-review:{message.id}",
            )
            return PipelineJobStatus.SKIPPED.value, f"Needs review: {', '.join(problems)}."
        if not in_send_window(self.settings):
            raise RetryLater("Outside the send window.", minutes=30)
        from app.services.automation_config import ExclusionSet, get_config
        from app.services.outreach_policy import first_emails_sent_today

        excluded = ExclusionSet.load(self.session).match_lead(lead)
        if excluded:
            return PipelineJobStatus.SKIPPED.value, excluded
        limit = get_config(self.session).outreach_daily_limit
        cap = self.settings.outreach_daily_send_cap
        if limit and first_emails_sent_today(self.session) >= limit:
            raise RetryLater("Daily outreach limit reached.", minutes=60)
        if cap and sent_today(self.session) >= cap:
            raise RetryLater("Daily send limit reached.", minutes=60)
        try:
            sent = GmailMailService(self.session, self.settings).send(
                lead.id,
                LeadEmailSendRequest(
                    subject=message.subject or "",
                    body=message.message or "",
                    outreach_message_id=message.id,
                    idempotency_key=f"auto-send:{message.id}",
                ),
            )
        except AppError as exc:
            if exc.code in {"GMAIL_NOT_CONNECTED", "GMAIL_NEEDS_REAUTH", "SEND_CAP_REACHED"}:
                raise RetryLater(exc.message, minutes=60) from exc
            if exc.code in {"DO_NOT_CONTACT", "EMAIL_SUPPRESSED", "COUNTRY_BLOCKED"}:
                return PipelineJobStatus.SKIPPED.value, exc.message
            raise
        schedule_followup_sequence(self.session, lead, message.id, sent.occurred_at)
        self.session.commit()
        return PipelineJobStatus.DONE.value, "Email sent. Follow-ups scheduled for Day 4, 10 and 20."

    # ------------------------------------------------------------------ helpers

    def _excluded(self, lead: Lead) -> str | None:
        if self.session is None:
            return None
        if self._exclusion_cache is None:
            from app.services.automation_config import ExclusionSet

            try:
                self._exclusion_cache = ExclusionSet.load(self.session)
            except Exception:
                return None
        return self._exclusion_cache.match_lead(lead)

    def _auto_send_enabled(self) -> bool:
        if self.session is None:
            return False
        try:
            from app.services.automation import get_flags

            return get_flags(self.session)["auto_send_enabled"]
        except Exception:
            return False

    def _has_unsent_draft(self, lead_id: UUID) -> bool:
        from app.models.enums import OutreachStatus

        count = self.session.scalar(
            select(func.count())
            .select_from(OutreachMessage)
            .where(
                OutreachMessage.lead_id == lead_id,
                OutreachMessage.status.in_([OutreachStatus.DRAFT.value, OutreachStatus.READY.value]),
            )
        )
        return bool(count)

    def _qualify(self, lead: Lead) -> None:
        if lead.lead_status == LeadStatus.NEW.value:
            lead.lead_status = LeadStatus.QUALIFIED.value
            self.activities.add(
                lead.id,
                "status_changed",
                "Status changed",
                description="NEW to QUALIFIED (automatic, score above threshold)",
                details={"from": "NEW", "to": "QUALIFIED"},
            )
            self._notify(
                lead,
                NotificationType.LEAD_QUALIFIED,
                "Lead qualified",
                f"{lead.business_name} passed the score threshold and entered the pipeline.",
                NotificationPriority.LOW,
                dedup_key=f"qualified:{lead.id}",
            )
        self._notify_high_opportunity(lead)

    def _notify_high_opportunity(self, lead: Lead) -> None:
        if (lead.lead_score or 0) >= HIGH_OPPORTUNITY_SCORE:
            self._notify(
                lead,
                NotificationType.HIGH_OPPORTUNITY_LEAD,
                "High-opportunity lead",
                f"{lead.business_name} scored {lead.lead_score}.",
                NotificationPriority.HIGH,
                dedup_key=f"high-opportunity:{lead.id}",
            )

    def _refresh_score(self, lead: Lead) -> None:
        from app.services.lead_intelligence import LeadIntelligenceService

        try:
            LeadIntelligenceService(self.session).get_intelligence(lead.id, persist_score=True)
            self.session.flush()
            self._notify_high_opportunity(lead)
        except Exception:
            logger.warning("pipeline_score_refresh_failed lead_id=%s", lead.id)

    def _notify(
        self,
        lead: Lead,
        kind: NotificationType,
        title: str,
        message: str,
        priority: NotificationPriority,
        *,
        dedup_key: str,
    ) -> None:
        try:
            from app.services.notifications import NotificationService

            with self.session.begin_nested():
                NotificationService(self.session, self.settings).create_notification(
                    type=kind,
                    title=title,
                    message=message,
                    priority=priority,
                    lead_id=lead.id,
                    action_url=f"/leads/{lead.id}",
                    dedup_key=dedup_key,
                )
        except Exception:
            logger.warning("pipeline_notification_failed type=%s", kind.value)

    def _has_ready_mockup(self, lead_id: UUID) -> bool:
        count = self.session.scalar(
            select(func.count())
            .select_from(Mockup)
            .where(Mockup.lead_id == lead_id, Mockup.status == MockupStatus.READY.value)
        )
        return bool(count)

    def _has_outreach(self, lead_id: UUID) -> bool:
        count = self.session.scalar(
            select(func.count())
            .select_from(OutreachMessage)
            .where(OutreachMessage.lead_id == lead_id)
        )
        return bool(count)

    def _latest_completed_audit(self, lead_id: UUID) -> WebsiteAudit | None:
        return self.session.scalar(
            select(WebsiteAudit)
            .where(
                WebsiteAudit.lead_id == lead_id,
                WebsiteAudit.status == AuditStatus.COMPLETED.value,
            )
            .order_by(WebsiteAudit.created_at.desc())
            .limit(1)
        )


def run_tick(
    session_factory: sessionmaker[Session],
    settings: Settings,
    *,
    time_budget_seconds: float = 200.0,
    heavy_cutoff_seconds: float = 110.0,
) -> TickSummary:
    """One cron tick. Safe to run at any time; overlapping ticks never share a job."""
    from app.models.enums import AutomationRunStatus
    from app.services.automation_config import (
        another_tick_running,
        claim_run,
        effective_settings,
        finish_run,
        mark_stale_runs,
    )

    summary = TickSummary()
    if not settings.pipeline_enabled:
        summary.stopped_because = "pipeline disabled"
        return summary
    with session_factory() as session:
        mark_stale_runs(session)
        if another_tick_running(session):
            session.commit()
            summary.stopped_because = "another tick is still running"
            return summary
        # One run per 5-minute window: a duplicate trigger or retry cannot run twice.
        run = claim_run(session, "tick", f"tick:{int(time.time() // 300)}")
        if run is None:
            session.commit()
            summary.stopped_because = "this window already ran"
            return summary
        settings, config = effective_settings(session, settings)
        run_id = run.id
        session.commit()
    if config.paused:
        summary.stopped_because = "automation is paused"
        _close_run(session_factory, run_id, AutomationRunStatus.SKIPPED, summary, None)
        return summary
    try:
        _run_tick_body(
            session_factory, settings, config, summary, time_budget_seconds, heavy_cutoff_seconds
        )
        from app.services.daily_report import maybe_send_daily_report

        try:
            summary.report = maybe_send_daily_report(session_factory, settings, config)
        except Exception:
            logger.exception("pipeline_report_failed")
            summary.report = "failed"
        from app.services.learning import maybe_update_learning

        try:
            summary.learning = maybe_update_learning(session_factory, config)
        except Exception:
            logger.exception("pipeline_learning_failed")
            summary.learning = "failed"
    except Exception as exc:
        logger.exception("pipeline_tick_failed")
        _close_run(session_factory, run_id, AutomationRunStatus.FAILED, summary, str(exc))
        return summary
    status = AutomationRunStatus.FAILED if summary.jobs_failed else AutomationRunStatus.OK
    _close_run(session_factory, run_id, status, summary, None)
    return summary


def _close_run(
    session_factory: sessionmaker[Session],
    run_id: UUID,
    status: Any,
    summary: TickSummary,
    error: str | None,
) -> None:
    from app.models.automation import AutomationRun
    from app.services.automation_config import finish_run

    try:
        with session_factory() as session:
            run = session.get(AutomationRun, run_id)
            if run is not None:
                finish_run(session, run, status, summary=summary.as_dict(), error=error)
            session.commit()
    except Exception:
        logger.exception("pipeline_close_run_failed")


def _run_tick_body(
    session_factory: sessionmaker[Session],
    settings: Settings,
    config: Any,
    summary: TickSummary,
    time_budget_seconds: float,
    heavy_cutoff_seconds: float,
) -> None:
    from app.services.discovery_engine import run_discovery_slice

    started = time.monotonic()
    # Find new leads first, so they can enter the pipeline in this same tick.
    try:
        summary.discovery = run_discovery_slice(
            session_factory, settings, config, max_cells=1
        ).as_dict()
    except Exception:
        logger.exception("pipeline_discovery_failed")
        summary.discovery = {"errors": ["Discovery stopped because of an unexpected error."]}
    with session_factory() as session:
        service = PipelineService(session, settings)
        summary.stale_recovered = service.recover_stale()
        summary.followups_due = service.sweep_followups()
        summary.leads_examined, summary.jobs_queued = service.sweep_leads()
        session.commit()

    while True:
        elapsed = time.monotonic() - started
        if elapsed >= time_budget_seconds:
            summary.stopped_because = "time budget used"
            break
        with session_factory() as session:
            service = PipelineService(session, settings)
            job = service.claim_next(allow_heavy=elapsed < heavy_cutoff_seconds)
            if job is None:
                break
            step = job.step
            outcome = service.run_job(job.id)
        summary.jobs_run += 1
        summary.steps.append(f"{step}:{outcome}")
        if outcome == PipelineJobStatus.DONE.value:
            summary.jobs_done += 1
        elif outcome == PipelineJobStatus.SKIPPED.value:
            summary.jobs_skipped += 1
        elif outcome == PipelineJobStatus.FAILED.value:
            summary.jobs_failed += 1
    _finish_tick(session_factory, settings, summary, started, time_budget_seconds)


def _finish_tick(
    session_factory: sessionmaker[Session],
    settings: Settings,
    summary: TickSummary,
    started: float,
    time_budget_seconds: float,
) -> None:
    from app.services.automation import process_due_followups, record_tick

    try:
        if time.monotonic() - started < time_budget_seconds:
            with session_factory() as session:
                outcome = process_due_followups(session, settings)
                session.commit()
            summary.followups_sent = outcome["sent"]
            summary.followups_waiting = outcome["waiting"]
    except Exception:
        logger.exception("pipeline_followups_failed")
    try:
        with session_factory() as session:
            record_tick(session, summary.as_dict())
            session.commit()
    except Exception:
        logger.exception("pipeline_record_tick_failed")

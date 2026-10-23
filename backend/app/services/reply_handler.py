"""Intelligent Reply Handler inspired by Harvey's Handler Agent.

Classifies incoming email replies across 11 intent categories:
- INTERESTED
- QUESTION
- POSITIVE
- OBJECTION
- PRICING
- NOT_INTERESTED
- WRONG_PERSON
- UNSUBSCRIBE
- OUT_OF_OFFICE
- MEETING_REQUEST
- OTHER

Extracts sentiment, identifies objection categories, recommends conversation stage
transitions with full audit trail, and generates human-in-the-loop suggested response drafts.
"""

from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any
from uuid import UUID

import httpx
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import Settings, get_settings
from app.models.enums import LeadStatus
from app.models.lead import Lead
from app.models.mockup import Mockup
from app.models.outreach import OutreachMessage
from app.repositories.activities import ActivityRepository
from app.services.knowledge import sales_knowledge
from app.services.persistence import flush_or_reject

logger = logging.getLogger(__name__)

INTENT_CATEGORIES = (
    "Interested",
    "Question",
    "Positive",
    "Objection",
    "Pricing",
    "Not Interested",
    "Wrong Person",
    "Unsubscribe",
    "Out of Office",
    "Meeting Request",
    "Other",
)

# Heuristic indicator regex patterns for fast resilient classification
_OOO_PATTERN = re.compile(
    r"(out\s+of\s+office|automatic\s+reply|auto[\s-]?reply|away\s+from\s+(the\s+)?office|"
    r"vacation\s+reply|annual\s+leave|currently\s+away)",
    re.I,
)
_UNSUB_PATTERN = re.compile(
    r"(unsubscribe|opt[\s-]?out|remove\s+me|take\s+me\s+off|stop\s+(emailing|contacting)|"
    r"do\s+not\s+(email|contact)|never\s+contact)",
    re.I,
)
_PRICING_PATTERN = re.compile(
    r"(how\s+much|cost|price|pricing|rates|fee|charge|budget|quote)",
    re.I,
)
_MEETING_PATTERN = re.compile(
    r"(calendar|schedule|meeting|call|phone\s+call|zoom|google\s+meet|chat\s+this\s+week|"
    r"available\s+on|let's\s+talk|hop\s+on\s+a\s+call)",
    re.I,
)
_WRONG_PERSON_PATTERN = re.compile(
    r"(wrong\s+person|no\s+longer\s+with|not\s+the\s+right\s+person|left\s+the\s+company|"
    r"contact\s+instead|reach\s+out\s+to)",
    re.I,
)
_NOT_INTERESTED_PATTERN = re.compile(
    r"(not\s+interested|no\s+thanks|not\s+looking|pass|all\s+set|don't\s+need|happy\s+with)",
    re.I,
)
_POSITIVE_INTEREST_PATTERN = re.compile(
    r"(send\s+(it\s+)?over|take\s+a\s+look|sounds\s+good|sounds\s+interesting|preview|"
    r"would\s+love\s+to\s+see|show\s+me|share\s+the\s+link)",
    re.I,
)


@dataclass(frozen=True)
class ReplyAnalysis:
    intent: str  # One of INTENT_CATEGORIES
    sentiment: str  # "positive" | "neutral" | "negative"
    confidence: float
    summary: str
    suggested_stage: str
    recommended_action: str
    suggested_response_subject: str | None
    suggested_response_body: str | None

    def to_dict(self) -> dict[str, Any]:
        return {
            "intent": self.intent,
            "sentiment": self.sentiment,
            "confidence": round(self.confidence, 2),
            "summary": self.summary,
            "suggested_stage": self.suggested_stage,
            "recommended_action": self.recommended_action,
            "suggested_response_subject": self.suggested_response_subject,
            "suggested_response_body": self.suggested_response_body,
        }


class ReplyHandlerService:
    def __init__(self, session: Session, settings: Settings | None = None) -> None:
        self.session = session
        self.settings = settings or get_settings()
        self.activities = ActivityRepository(session)

    def analyze_reply(
        self,
        lead_id: UUID,
        *,
        subject: str | None,
        body_text: str | None,
        sender_email: str | None = None,
    ) -> ReplyAnalysis:
        lead = self.session.get(Lead, lead_id)
        if lead is None:
            return self._heuristic_analysis(subject, body_text, None)

        mockup = self._get_lead_mockup(lead_id)
        mockup_url = f"/mockups/{mockup.id}" if mockup else None

        analysis = self._llm_analysis(
            lead=lead,
            subject=subject,
            body_text=body_text,
            mockup_url=mockup_url,
        )
        if analysis is None:
            analysis = self._heuristic_analysis(subject, body_text, lead, mockup_url)

        return analysis

    def analyze_and_process_reply(
        self,
        lead_id: UUID,
        *,
        subject: str | None,
        body_text: str | None,
        sender_email: str | None,
    ) -> ReplyAnalysis:
        lead = self.session.get(Lead, lead_id)
        analysis = self.analyze_reply(
            lead_id,
            subject=subject,
            body_text=body_text,
            sender_email=sender_email,
        )
        if lead is not None:
            self._apply_reply_effects(lead, analysis, subject, body_text)
        return analysis

    def _apply_reply_effects(
        self,
        lead: Lead,
        analysis: ReplyAnalysis,
        subject: str | None,
        body_text: str | None,
    ) -> None:
        now = datetime.now(UTC)
        lead.last_replied_at = now
        lead.email_unread = True

        previous_stage = lead.lead_status

        # Validate stage transitions (Human-in-the-loop: mark as REPLIED and recommend stage)
        if analysis.intent == "Unsubscribe":
            lead.do_not_contact = True
            lead.lead_status = LeadStatus.DO_NOT_CONTACT.value
        elif lead.lead_status not in {
            LeadStatus.MEETING.value,
            LeadStatus.WON.value,
            LeadStatus.LOST.value,
            LeadStatus.DO_NOT_CONTACT.value,
        }:
            lead.lead_status = LeadStatus.REPLIED.value

        flush_or_reject(self.session)

        # Record activity with audit trail
        self.activities.add(
            lead.id,
            "reply_analyzed",
            f"Reply Classified: {analysis.intent}",
            description=analysis.summary,
            details={
                "intent": analysis.intent,
                "sentiment": analysis.sentiment,
                "confidence": analysis.confidence,
                "suggested_stage": analysis.suggested_stage,
                "previous_stage": previous_stage,
                "current_stage": lead.lead_status,
                "recommended_action": analysis.recommended_action,
                "snippet": (body_text or "")[:200],
            },
        )

    def _llm_analysis(
        self,
        lead: Lead,
        subject: str | None,
        body_text: str | None,
        mockup_url: str | None,
    ) -> ReplyAnalysis | None:
        gemini_ready = bool(self.settings.gemini_api_key.strip())
        groq_ready = bool(self.settings.groq_api_key.strip())
        if not (gemini_ready or groq_ready):
            return None

        objection_playbook = sales_knowledge.get_objection_handling()
        content = f"Subject: {subject or ''}\nBody:\n{body_text or ''}".strip()

        prompt = (
            "You are a Senior B2B Sales Assistant & Conversation Handler (Harvey Agent).\n"
            f"Analyze an inbound email reply received from '{lead.business_name}' "
            f"(Industry: {lead.industry or 'Unknown'}, City: {lead.city or ''}).\n\n"
            f"INBOUND REPLY CONTENT:\n{content}\n\n"
            f"OBJECTION & RESPONSE GUIDELINES:\n{objection_playbook}\n\n"
            "INSTRUCTIONS:\n"
            "1. Classify intent strictly into one of: "
            "['Interested', 'Question', 'Positive', 'Objection', 'Pricing', "
            "'Not Interested', 'Wrong Person', 'Unsubscribe', 'Out of Office', 'Meeting Request', 'Other'].\n"
            "2. Determine sentiment: 'positive', 'neutral', or 'negative'.\n"
            "3. Summarize the prospect's stance in 1 sentence.\n"
            "4. Suggest next conversation stage: ['Interested', 'Meeting Requested', 'Nurture', 'Lost', 'Unsubscribe', 'Outreach Ready'].\n"
            "5. Recommend next action for the user (e.g. 'Answer pricing question and propose a 10-minute call').\n"
            "6. Draft a suggested human response under 70 words adhering strictly to the objection guidelines. "
            "Never sound defensive, keep it friendly and peer-to-peer.\n\n"
            "Respond in clean JSON format matching this schema:\n"
            "{\n"
            '  "intent": "Interested",\n'
            '  "sentiment": "positive",\n'
            '  "confidence": 0.95,\n'
            '  "summary": "Prospect is curious to see the mockup and asks for details.",\n'
            '  "suggested_stage": "Interested",\n'
            '  "recommended_action": "Send the mockup link and propose a short call.",\n'
            '  "suggested_response_subject": "Re: ...",\n'
            '  "suggested_response_body": "Hi there,\\n\\n..."\n'
            "}\n"
        )

        try:
            with httpx.Client(timeout=30.0) as client:
                raw_json = None
                if gemini_ready:
                    raw_json = self._call_gemini(client, prompt)
                if not raw_json and groq_ready:
                    raw_json = self._call_groq(client, prompt)

                if raw_json:
                    data = json.loads(raw_json)
                    intent = data.get("intent") or "Other"
                    if intent not in INTENT_CATEGORIES:
                        intent = "Other"
                    return ReplyAnalysis(
                        intent=intent,
                        sentiment=data.get("sentiment") or "neutral",
                        confidence=float(data.get("confidence") or 0.85),
                        summary=data.get("summary") or "Inbound reply received.",
                        suggested_stage=data.get("suggested_stage") or "Replied",
                        recommended_action=data.get("recommended_action") or "Review and respond.",
                        suggested_response_subject=data.get("suggested_response_subject"),
                        suggested_response_body=data.get("suggested_response_body"),
                    )
        except Exception as exc:
            logger.warning("llm_reply_classification_failed: %s", exc)

        return None

    def _heuristic_analysis(
        self,
        subject: str | None,
        body_text: str | None,
        lead: Lead | None,
        mockup_url: str | None = None,
    ) -> ReplyAnalysis:
        combined = f"{subject or ''} {body_text or ''}".lower()
        biz_name = lead.business_name if lead else "your business"
        re_subj = f"Re: {subject}" if subject and not subject.lower().startswith("re:") else (subject or "Following up")

        if _UNSUB_PATTERN.search(combined):
            return ReplyAnalysis(
                intent="Unsubscribe",
                sentiment="negative",
                confidence=0.96,
                summary="Prospect requested to unsubscribe or be removed from outreach.",
                suggested_stage="Unsubscribe",
                recommended_action="Lead marked as Do Not Contact. No response needed.",
                suggested_response_subject=None,
                suggested_response_body=None,
            )

        if _OOO_PATTERN.search(combined):
            return ReplyAnalysis(
                intent="Out of Office",
                sentiment="neutral",
                confidence=0.95,
                summary="Automated out-of-office autoreply detected.",
                suggested_stage="Replied",
                recommended_action="Wait for prospect to return; followup scheduled.",
                suggested_response_subject=None,
                suggested_response_body=None,
            )

        if _MEETING_PATTERN.search(combined):
            return ReplyAnalysis(
                intent="Meeting Request",
                sentiment="positive",
                confidence=0.92,
                summary="Prospect suggested or agreed to schedule a call/meeting.",
                suggested_stage="Meeting Requested",
                recommended_action="Confirm meeting time and send calendar invite.",
                suggested_response_subject=re_subj,
                suggested_response_body=(
                    f"Hi there,\n\nThanks for getting back to me! I would be glad to connect. "
                    f"Does Thursday at 2 PM or Friday morning work for a quick 10-minute chat?\n\nBest,\nIbrar"
                ),
            )

        if _PRICING_PATTERN.search(combined):
            return ReplyAnalysis(
                intent="Pricing",
                sentiment="neutral",
                confidence=0.90,
                summary="Prospect asked about price, rates, or project cost.",
                suggested_stage="Interested",
                recommended_action="Answer pricing clearly ($550–$850 flat) and propose viewing the concept.",
                suggested_response_subject=re_subj,
                suggested_response_body=(
                    f"Hi there,\n\nOur homepage redesigns are a flat $750 (or $850 for a full build), "
                    f"including mobile optimization and direct appointment integration with zero retainers.\n\n"
                    f"I already have a concept preview ready for {biz_name}. "
                    f"Would you be open to a quick 5-minute glance this week?\n\nBest,\nIbrar"
                ),
            )

        if _WRONG_PERSON_PATTERN.search(combined):
            return ReplyAnalysis(
                intent="Wrong Person",
                sentiment="neutral",
                confidence=0.88,
                summary="Recipient indicated they are not the appropriate contact.",
                suggested_stage="Lost",
                recommended_action="Ask for correct decision maker or archive lead.",
                suggested_response_subject=re_subj,
                suggested_response_body=(
                    "Hi there,\n\nThanks for letting me know! Could you point me toward who manages "
                    f"digital presence and marketing for {biz_name}?\n\nAppreciate your time!\n\nBest,\nIbrar"
                ),
            )

        if _NOT_INTERESTED_PATTERN.search(combined):
            return ReplyAnalysis(
                intent="Not Interested",
                sentiment="negative",
                confidence=0.88,
                summary="Prospect indicated they are not interested at this time.",
                suggested_stage="Lost",
                recommended_action="Send courteous acknowledgement and move to nurture.",
                suggested_response_subject=re_subj,
                suggested_response_body=(
                    f"Hi there,\n\nUnderstood — thanks for letting me know! "
                    f"If you ever decide to refresh {biz_name}'s website down the road, feel free to reach out anytime.\n\n"
                    f"Wishing you continued success!\n\nBest,\nIbrar"
                ),
            )

        if _POSITIVE_INTEREST_PATTERN.search(combined):
            return ReplyAnalysis(
                intent="Interested",
                sentiment="positive",
                confidence=0.92,
                summary="Prospect is receptive and open to viewing the preview or details.",
                suggested_stage="Interested",
                recommended_action="Send mockup concept link and propose short walkthrough.",
                suggested_response_subject=re_subj,
                suggested_response_body=(
                    f"Hi there,\n\nGlad to hear from you! Here is the concept preview I put together for {biz_name}:\n"
                    f"{mockup_url or 'Preview available'}\n\n"
                    f"Key improvements include direct mobile booking and prominent review proof. "
                    f"Let me know what you think!\n\nBest,\nIbrar"
                ),
            )

        # Default fallback
        return ReplyAnalysis(
            intent="Question",
            sentiment="neutral",
            confidence=0.75,
            summary="Prospect sent a general reply or inquiry.",
            suggested_stage="Replied",
            recommended_action="Review reply details and draft response.",
            suggested_response_subject=re_subj,
            suggested_response_body=f"Hi there,\n\nThanks for your note regarding {biz_name}. ...",
        )

    def _get_lead_mockup(self, lead_id: UUID) -> Mockup | None:
        statement = select(Mockup).where(Mockup.lead_id == lead_id).order_by(Mockup.version.desc())
        rows = list(self.session.scalars(statement))
        return rows[0] if rows else None

    def _call_gemini(self, client: httpx.Client, prompt: str) -> str | None:
        url = (
            f"https://generativelanguage.googleapis.com/v1beta/models/"
            f"{self.settings.gemini_model}:generateContent?key={self.settings.gemini_api_key}"
        )
        payload = {
            "contents": [{"parts": [{"text": prompt}]}],
            "generationConfig": {
                "temperature": 0.2,
                "responseMimeType": "application/json",
            },
        }
        resp = client.post(url, json=payload)
        if resp.status_code == 200:
            result = resp.json()
            candidates = result.get("candidates", [])
            if candidates:
                parts = candidates[0].get("content", {}).get("parts", [])
                if parts:
                    return parts[0].get("text")
        return None

    def _call_groq(self, client: httpx.Client, prompt: str) -> str | None:
        url = "https://api.groq.com/openai/v1/chat/completions"
        headers = {
            "Authorization": f"Bearer {self.settings.groq_api_key}",
            "Content-Type": "application/json",
        }
        payload = {
            "model": self.settings.groq_model,
            "messages": [{"role": "user", "content": prompt}],
            "temperature": 0.2,
            "response_format": {"type": "json_object"},
        }
        resp = client.post(url, headers=headers, json=payload)
        if resp.status_code == 200:
            data = resp.json()
            choices = data.get("choices", [])
            if choices:
                return choices[0].get("message", {}).get("content")
        return None

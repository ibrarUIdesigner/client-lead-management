from __future__ import annotations

import logging
import re
from dataclasses import dataclass

from app.models.enums import EmailClassification

logger = logging.getLogger(__name__)

_OOO_SUBJECT = re.compile(
    r"(out\s+of\s+office|automatic\s+reply|auto[\s-]?reply|away\s+from\s+(the\s+)?office|"
    r"vacation\s+reply|abwesend|abwesenheit)",
    re.I,
)
_OOO_HEADERS = re.compile(r"(auto-replied|auto-generated)", re.I)
_BOUNCE_SENDERS = re.compile(
    r"(mailer-daemon|postmaster|mail-daemon|noreply-bounce)@",
    re.I,
)
_BOUNCE_SUBJECT = re.compile(
    r"(delivery\s+status\s+notification|undeliverable|mail\s+delivery\s+failed|"
    r"returned\s+mail|failure\s+notice|delivery\s+failure)",
    re.I,
)
_OPT_OUT = re.compile(
    r"("
    r"unsubscribe|"
    r"opt[\s-]?out|"
    r"do\s+not\s+(email|contact|reach)|"
    r"remove\s+me|"
    r"stop\s+(emailing|contacting)|"
    r"take\s+me\s+off|"
    r"never\s+contact"
    r")",
    re.I,
)


@dataclass(frozen=True)
class ClassificationResult:
    classification: EmailClassification
    reason: str


def classify_inbound_message(
    *,
    subject: str | None,
    body_text: str | None,
    sender_email: str | None,
    auto_submitted: str | None = None,
    precedence: str | None = None,
) -> ClassificationResult:
    sender = (sender_email or "").lower()
    subject_text = subject or ""
    body = body_text or ""
    combined = f"{subject_text}\n{body}"

    if _BOUNCE_SENDERS.search(sender) or _BOUNCE_SUBJECT.search(subject_text):
        return ClassificationResult(EmailClassification.BOUNCE, "bounce_indicators")

    if (
        (auto_submitted and _OOO_HEADERS.search(auto_submitted))
        or (precedence and precedence.lower() in {"bulk", "auto_reply", "junk"})
        or _OOO_SUBJECT.search(subject_text)
    ):
        return ClassificationResult(EmailClassification.OUT_OF_OFFICE, "ooo_indicators")

    if _OPT_OUT.search(combined):
        return ClassificationResult(EmailClassification.OPT_OUT, "opt_out_language")

    return ClassificationResult(EmailClassification.HUMAN_REPLY, "default_human")

import re

from app.models.enums import LeadStatus

_TOKEN = re.compile(r"\{([a-z_]+)\}")

BUILTIN_SUBJECT = "A clearer homepage for {business}"
BUILTIN_BODY = (
    "Hi {name},\n\n"
    "I put together a homepage concept for {business}. {findings}\n\n"
    "Happy to walk through it if it is useful.\n"
)
FALLBACK_FINDINGS = "The current page could make the next step easier to find."

_RANK = {
    LeadStatus.NEW.value: 0,
    LeadStatus.QUALIFIED.value: 1,
    LeadStatus.AUDIT_PENDING.value: 2,
    LeadStatus.AUDIT_COMPLETE.value: 3,
    LeadStatus.MOCKUP_PENDING.value: 4,
    LeadStatus.MOCKUP_READY.value: 5,
    LeadStatus.CONTACTED.value: 6,
    LeadStatus.FOLLOW_UP.value: 7,
    LeadStatus.REPLIED.value: 8,
    LeadStatus.MEETING.value: 9,
    LeadStatus.PROPOSAL.value: 10,
    LeadStatus.WON.value: 11,
    LeadStatus.LOST.value: 11,
    LeadStatus.NOT_INTERESTED.value: 11,
}
_TERMINAL = {
    LeadStatus.WON.value,
    LeadStatus.LOST.value,
    LeadStatus.NOT_INTERESTED.value,
}


def render_template(template: str | None, context: dict[str, str]) -> str:
    if not template:
        return ""

    def replace(match: re.Match[str]) -> str:
        key = match.group(1)
        if key in context:
            return context[key]
        return match.group(0)

    return _TOKEN.sub(replace, template)


def findings_text(issues: list[object] | None) -> str | None:
    titles: list[str] = []
    for issue in issues or []:
        title = _issue_title(issue)
        if title and title not in titles:
            titles.append(title)
        if len(titles) == 2:
            break
    if not titles:
        return None
    return " and ".join(titles)


def compose_outreach(
    subject_template: str | None,
    body_template: str | None,
    *,
    business: str,
    name: str | None,
    industry: str | None,
    website: str | None,
    mockup: str | None,
    audit_findings: str | None,
) -> tuple[str, str]:
    context = {
        "business": business,
        "name": (name or "").strip() or "there",
        "industry": (industry or "").strip() or "your industry",
        "website": (website or "").strip() or "the current website",
        "findings": audit_findings or FALLBACK_FINDINGS,
        "mockup": (mockup or "").strip() or "a homepage concept",
    }
    subject = render_template(subject_template or BUILTIN_SUBJECT, context).strip()
    if not subject:
        subject = render_template(BUILTIN_SUBJECT, context).strip()
    body = _compose_body(body_template or BUILTIN_BODY, context, audit_findings)
    return subject, body


def next_lead_status(current: str, target: LeadStatus) -> str | None:
    if current in _TERMINAL:
        return None
    current_rank = _RANK.get(current)
    if current_rank is None or current_rank >= _RANK[target]:
        return None
    return target.value


def _compose_body(
    template_body: str,
    context: dict[str, str],
    audit_findings: str | None,
) -> str:
    rendered = render_template(template_body, context).strip()
    if audit_findings and "{findings}" not in template_body:
        extra = f"What stood out: {audit_findings}."
        rendered = f"{rendered}\n\n{extra}" if rendered else extra
    if rendered and not rendered.endswith("\n"):
        rendered = f"{rendered}\n"
    return rendered


def _issue_title(issue: object) -> str | None:
    if isinstance(issue, str):
        title = issue.strip()
        return title or None
    if isinstance(issue, dict):
        raw = issue.get("title") or issue.get("detail")
        if isinstance(raw, str) and raw.strip():
            return raw.strip()
    return None

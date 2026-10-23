from enum import StrEnum


class LeadStatus(StrEnum):
    NEW = "NEW"
    QUALIFIED = "QUALIFIED"
    AUDIT_PENDING = "AUDIT_PENDING"
    AUDIT_COMPLETE = "AUDIT_COMPLETE"
    MOCKUP_PENDING = "MOCKUP_PENDING"
    MOCKUP_READY = "MOCKUP_READY"
    CONTACTED = "CONTACTED"
    FOLLOW_UP = "FOLLOW_UP"
    REPLIED = "REPLIED"
    MEETING = "MEETING"
    PROPOSAL = "PROPOSAL"
    WON = "WON"
    LOST = "LOST"
    NOT_INTERESTED = "NOT_INTERESTED"
    DO_NOT_CONTACT = "DO_NOT_CONTACT"


class GmailAccountStatus(StrEnum):
    ACTIVE = "ACTIVE"
    NEEDS_REAUTH = "NEEDS_REAUTH"
    DISCONNECTED = "DISCONNECTED"


class EmailDirection(StrEnum):
    OUTBOUND = "OUTBOUND"
    INBOUND = "INBOUND"


class EmailClassification(StrEnum):
    OUTGOING = "OUTGOING"
    HUMAN_REPLY = "HUMAN_REPLY"
    OUT_OF_OFFICE = "OUT_OF_OFFICE"
    BOUNCE = "BOUNCE"
    OPT_OUT = "OPT_OUT"
    AMBIGUOUS = "AMBIGUOUS"
    OTHER = "OTHER"


class AuditStatus(StrEnum):
    PENDING = "PENDING"
    RUNNING = "RUNNING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"


class ResearchStatus(StrEnum):
    PENDING = "PENDING"
    RUNNING = "RUNNING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"


class MockupStatus(StrEnum):
    PENDING = "PENDING"
    GENERATING = "GENERATING"
    READY = "READY"
    FAILED = "FAILED"
    ARCHIVED = "ARCHIVED"


class OutreachStatus(StrEnum):
    DRAFT = "DRAFT"
    READY = "READY"
    SENT = "SENT"
    OPENED = "OPENED"
    REPLIED = "REPLIED"
    BOUNCED = "BOUNCED"
    CANCELLED = "CANCELLED"


class FollowupStatus(StrEnum):
    SCHEDULED = "SCHEDULED"
    DUE = "DUE"
    COMPLETED = "COMPLETED"
    CANCELLED = "CANCELLED"


class DiscoveryRunStatus(StrEnum):
    RUNNING = "RUNNING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"


class DiscoveryTrigger(StrEnum):
    DAILY = "daily"
    MANUAL = "manual"


class ApifyRunStatus(StrEnum):
    READY = "READY"
    RUNNING = "RUNNING"
    SUCCEEDED = "SUCCEEDED"
    FAILED = "FAILED"
    TIMING_OUT = "TIMING-OUT"
    TIMED_OUT = "TIMED-OUT"
    ABORTING = "ABORTING"
    ABORTED = "ABORTED"


class NotificationType(StrEnum):
    NEW_EMAIL_REPLY = "NEW_EMAIL_REPLY"
    POSITIVE_REPLY = "POSITIVE_REPLY"
    OBJECTION_REPLY = "OBJECTION_REPLY"
    MEETING_REQUEST = "MEETING_REQUEST"
    FOLLOWUP_DUE = "FOLLOWUP_DUE"
    MOCKUP_READY = "MOCKUP_READY"
    RESEARCH_COMPLETE = "RESEARCH_COMPLETE"
    AUDIT_COMPLETE = "AUDIT_COMPLETE"
    EMAIL_DRAFT_READY = "EMAIL_DRAFT_READY"
    EMAIL_SEND_FAILED = "EMAIL_SEND_FAILED"
    LEAD_QUALIFIED = "LEAD_QUALIFIED"
    HIGH_OPPORTUNITY_LEAD = "HIGH_OPPORTUNITY_LEAD"
    APIFY_JOB_COMPLETE = "APIFY_JOB_COMPLETE"


class NotificationPriority(StrEnum):
    LOW = "LOW"
    NORMAL = "NORMAL"
    HIGH = "HIGH"
    URGENT = "URGENT"


def enum_values(enum_cls: type[StrEnum]) -> tuple[str, ...]:
    return tuple(item.value for item in enum_cls)

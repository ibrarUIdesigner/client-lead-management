export const LEAD_STATUS_VALUES = [
  "NEW",
  "QUALIFIED",
  "AUDIT_PENDING",
  "AUDIT_COMPLETE",
  "MOCKUP_PENDING",
  "MOCKUP_READY",
  "CONTACTED",
  "FOLLOW_UP",
  "REPLIED",
  "MEETING",
  "PROPOSAL",
  "WON",
  "LOST",
  "NOT_INTERESTED",
] as const;

export type LeadStatus = (typeof LEAD_STATUS_VALUES)[number];

const labels: Record<LeadStatus, string> = {
  NEW: "New",
  QUALIFIED: "Qualified",
  AUDIT_PENDING: "Audit pending",
  AUDIT_COMPLETE: "Audit complete",
  MOCKUP_PENDING: "Mockup pending",
  MOCKUP_READY: "Mockup ready",
  CONTACTED: "Contacted",
  FOLLOW_UP: "Follow-up",
  REPLIED: "Replied",
  MEETING: "Meeting",
  PROPOSAL: "Proposal",
  WON: "Won",
  LOST: "Lost",
  NOT_INTERESTED: "Not interested",
};

export const leadStatusOptions = LEAD_STATUS_VALUES.map((value) => ({
  value,
  label: labels[value],
}));

import type { ReactNode } from "react";

import { cn } from "../../lib/cn";

export type BadgeTone = "gray" | "indigo" | "blue" | "green" | "orange" | "red";

const tones: Record<BadgeTone, string> = {
  gray: "bg-gray-100 text-gray-700",
  indigo: "bg-primary-50 text-primary-700",
  blue: "bg-blue-50 text-blue-700",
  green: "bg-emerald-50 text-emerald-800",
  orange: "bg-amber-50 text-amber-800",
  red: "bg-red-50 text-red-700",
};

type BadgeProps = {
  tone?: BadgeTone;
  children: ReactNode;
};

export function Badge({ tone = "gray", children }: BadgeProps) {
  return (
    <span
      className={cn(
        "inline-flex items-center rounded-control px-2 py-1 text-caption font-medium",
        tones[tone],
      )}
    >
      {children}
    </span>
  );
}

const statusLabels: Record<string, string> = {
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
  DO_NOT_CONTACT: "Do not contact",
  RUNNING: "Running",
  SUCCEEDED: "Succeeded",
  FAILED: "Failed",
  "TIMING-OUT": "Timing out",
  "TIMED-OUT": "Timed out",
  ABORTING: "Aborting",
  ABORTED: "Aborted",
};

const statusTones: Record<string, BadgeTone> = {
  NEW: "gray",
  QUALIFIED: "indigo",
  AUDIT_PENDING: "indigo",
  AUDIT_COMPLETE: "indigo",
  MOCKUP_PENDING: "indigo",
  MOCKUP_READY: "indigo",
  CONTACTED: "blue",
  FOLLOW_UP: "blue",
  REPLIED: "green",
  MEETING: "orange",
  PROPOSAL: "orange",
  WON: "green",
  LOST: "red",
  NOT_INTERESTED: "gray",
  DO_NOT_CONTACT: "red",
  PENDING: "indigo",
  GENERATING: "indigo",
  READY: "green",
  FAILED: "red",
  RUNNING: "blue",
  SUCCEEDED: "green",
  "TIMING-OUT": "orange",
  "TIMED-OUT": "orange",
  ABORTING: "orange",
  ABORTED: "gray",
  ARCHIVED: "gray",
  DRAFT: "gray",
  SENT: "blue",
  OPENED: "blue",
  BOUNCED: "red",
  SCHEDULED: "indigo",
  DUE: "orange",
  COMPLETED: "green",
  CANCELLED: "gray",
};

type StatusBadgeProps = {
  status: string;
};

export function StatusBadge({ status }: StatusBadgeProps) {
  const label =
    statusLabels[status] ??
    status
      .toLowerCase()
      .split("_")
      .map((part) => part.charAt(0).toUpperCase() + part.slice(1))
      .join(" ");

  return <Badge tone={statusTones[status] ?? "gray"}>{label}</Badge>;
}

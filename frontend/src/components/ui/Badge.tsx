import type { ReactNode } from "react";

import { cn } from "../../lib/cn";

export type BadgeTone = "gray" | "indigo" | "blue" | "green" | "orange" | "red";

const tones: Record<BadgeTone, string> = {
  gray: "bg-gray-50 text-gray-700 ring-1 ring-inset ring-gray-400/25",
  indigo: "bg-primary-50 text-primary-700 ring-1 ring-inset ring-primary-500/25",
  blue: "bg-blue-50 text-blue-700 ring-1 ring-inset ring-blue-500/25",
  green: "bg-emerald-50 text-emerald-800 ring-1 ring-inset ring-emerald-500/25",
  orange: "bg-amber-50 text-amber-800 ring-1 ring-inset ring-amber-500/25",
  red: "bg-red-50 text-red-700 ring-1 ring-inset ring-red-500/25",
};

type BadgeProps = {
  tone?: BadgeTone;
  className?: string;
  children: ReactNode;
};

export function Badge({ tone = "gray", className, children }: BadgeProps) {
  return (
    <span
      className={cn(
        "inline-flex items-center gap-1.5 rounded-md px-2 py-0.5 text-[11px] font-semibold tracking-tight whitespace-nowrap",
        tones[tone],
        className,
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

const dotTones: Record<BadgeTone, string> = {
  gray: "bg-gray-400",
  indigo: "bg-primary-500",
  blue: "bg-blue-500",
  green: "bg-emerald-500",
  orange: "bg-amber-500",
  red: "bg-red-500",
};

export function StatusBadge({ status }: StatusBadgeProps) {
  const label =
    statusLabels[status] ??
    status
      .toLowerCase()
      .split("_")
      .map((part) => part.charAt(0).toUpperCase() + part.slice(1))
      .join(" ");

  const tone = statusTones[status] ?? "gray";

  return (
    <Badge tone={tone}>
      <span className={cn("size-1.5 rounded-full shrink-0", dotTones[tone])} aria-hidden="true" />
      <span>{label}</span>
    </Badge>
  );
}

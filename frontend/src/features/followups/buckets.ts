import type { FollowupItem } from "../../types/workspace";

export type FollowupBucket = "overdue" | "today" | "upcoming" | "done";

const viewedAt = Date.now();

export function followUpBucket(item: FollowupItem): FollowupBucket {
  if (item.status === "COMPLETED" || item.status === "CANCELLED") {
    return "done";
  }

  const when = new Date(item.scheduled_for).getTime();
  const start = new Date(viewedAt);
  start.setHours(0, 0, 0, 0);
  const end = start.getTime() + 24 * 60 * 60 * 1000;

  if (item.status === "DUE" || when < start.getTime()) {
    return "overdue";
  }
  if (when < end) {
    return "today";
  }
  return "upcoming";
}

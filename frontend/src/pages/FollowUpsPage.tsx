import { Link } from "react-router-dom";
import { AlertTriangle, CalendarClock, CheckCircle2, Clock } from "lucide-react";

import { QueryGate } from "../components/feedback/QueryGate";
import { PageHeader } from "../components/layout/PageHeader";
import { StatusBadge } from "../components/ui/Badge";
import { Card } from "../components/ui/Card";
import { followUpBucket, type FollowupBucket } from "../features/followups/buckets";
import { FollowUpActions } from "../features/followups/FollowUpActions";
import { useFollowups } from "../hooks/useWorkspace";
import { cn, focusRing } from "../lib/cn";
import { formatWhen } from "../lib/format";
import type { FollowupItem } from "../types/workspace";

const sections: {
  id: FollowupBucket;
  title: string;
  empty: string;
  icon: any;
  tone: string;
}[] = [
  {
    id: "overdue",
    title: "Overdue",
    empty: "You're caught up! Nothing is overdue.",
    icon: AlertTriangle,
    tone: "text-red-600 bg-red-50",
  },
  {
    id: "today",
    title: "Due Today",
    empty: "You're all caught up 🎉 No follow-ups are due today.",
    icon: Clock,
    tone: "text-orange-600 bg-orange-50",
  },
  {
    id: "upcoming",
    title: "Upcoming",
    empty: "No upcoming follow-ups scheduled.",
    icon: CalendarClock,
    tone: "text-blue-600 bg-blue-50",
  },
  {
    id: "done",
    title: "Completed",
    empty: "No completed follow-ups recorded yet.",
    icon: CheckCircle2,
    tone: "text-emerald-600 bg-emerald-50",
  },
];

export function FollowUpsPage() {
  const followups = useFollowups();
  const items = followups.data ?? [];

  const overdueCount = items.filter((i) => followUpBucket(i) === "overdue").length;
  const todayCount = items.filter((i) => followUpBucket(i) === "today").length;
  const upcomingCount = items.filter((i) => followUpBucket(i) === "upcoming").length;
  const completedCount = items.filter((i) => followUpBucket(i) === "done").length;

  return (
    <>
      <PageHeader
        title="Follow-ups"
        description="Structured check-in schedule for prospects you have already contacted to maximize reply rates."
      />

      {/* Summary KPI row */}
      <div className="mb-6 grid grid-cols-2 gap-3 sm:grid-cols-4">
        <div className="rounded-card border border-gray-200 bg-white p-3.5 shadow-2xs">
          <span className="text-caption font-semibold text-gray-500">Overdue</span>
          <p className={cn("mt-1 text-h3 font-bold tabular-nums", overdueCount > 0 ? "text-danger" : "text-ink")}>
            {overdueCount}
          </p>
        </div>
        <div className="rounded-card border border-gray-200 bg-white p-3.5 shadow-2xs">
          <span className="text-caption font-semibold text-gray-500">Due Today</span>
          <p className={cn("mt-1 text-h3 font-bold tabular-nums", todayCount > 0 ? "text-amber-600" : "text-ink")}>
            {todayCount}
          </p>
        </div>
        <div className="rounded-card border border-gray-200 bg-white p-3.5 shadow-2xs">
          <span className="text-caption font-semibold text-gray-500">Upcoming</span>
          <p className="mt-1 text-h3 font-bold tabular-nums text-ink">{upcomingCount}</p>
        </div>
        <div className="rounded-card border border-gray-200 bg-white p-3.5 shadow-2xs">
          <span className="text-caption font-semibold text-gray-500">Completed</span>
          <p className="mt-1 text-h3 font-bold tabular-nums text-emerald-700">{completedCount}</p>
        </div>
      </div>

      <QueryGate
        pending={followups.isPending}
        error={followups.error}
        onRetry={() => {
          void followups.refetch();
        }}
        fallback="Follow-ups could not be loaded."
      >
        {followups.data ? <FollowUpBoard items={followups.data} /> : null}
      </QueryGate>
    </>
  );
}

function FollowUpBoard({ items }: { items: FollowupItem[] }) {
  return (
    <div className="grid gap-4 lg:grid-cols-2">
      {sections.map((section) => {
        const rows = items.filter((item) => followUpBucket(item) === section.id);
        const Icon = section.icon;

        return (
          <Card key={section.id} className="shadow-sm">
            <div className="flex items-center justify-between gap-3 border-b border-gray-100 pb-3">
              <div className="flex items-center gap-2">
                <div className={cn("flex size-7 items-center justify-center rounded-lg", section.tone)}>
                  <Icon className="size-4" />
                </div>
                <h2 className="text-h4 font-bold text-ink">{section.title}</h2>
              </div>
              <span className="rounded-full bg-gray-100 px-2 py-0.5 text-caption font-bold text-gray-600">
                {rows.length}
              </span>
            </div>

            {rows.length === 0 ? (
              <p className="mt-6 py-6 text-center text-small text-gray-500 bg-gray-50/50 rounded-lg border border-dashed border-gray-200">
                {section.empty}
              </p>
            ) : (
              <ul className="mt-3 divide-y divide-gray-100">
                {rows.map((item) => (
                  <li key={item.id} className="py-3.5 first:pt-2">
                    <div className="flex flex-col gap-2 sm:flex-row sm:items-start sm:justify-between">
                      <div>
                        <Link
                          to={`/leads/${item.lead_id}`}
                          className={cn("text-body font-bold text-ink hover:text-primary-700", focusRing)}
                        >
                          {item.business_name}
                        </Link>
                        <p className="mt-0.5 text-caption text-gray-500">
                          {[item.city, typeLabel(item.type), formatWhen(item.scheduled_for)]
                            .filter(Boolean)
                            .join(" · ")}
                        </p>
                      </div>
                      <StatusBadge status={item.status} />
                    </div>
                    {item.notes ? (
                      <p className="mt-2 text-small text-gray-700 bg-gray-50 p-2 rounded border border-gray-100">
                        {item.notes}
                      </p>
                    ) : null}
                    <FollowUpActions item={item} />
                  </li>
                ))}
              </ul>
            )}
          </Card>
        );
      })}
    </div>
  );
}

function typeLabel(value: string | null): string | null {
  if (!value) {
    return null;
  }
  return value.charAt(0).toUpperCase() + value.slice(1);
}

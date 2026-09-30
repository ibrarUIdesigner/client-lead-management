import { Link } from "react-router-dom";

import { QueryGate } from "../components/feedback/QueryGate";
import { PageHeader } from "../components/layout/PageHeader";
import { StatusBadge } from "../components/ui/Badge";
import { Card } from "../components/ui/Card";
import { followUpBucket, type FollowupBucket } from "../features/followups/buckets";
import { useFollowups } from "../hooks/useWorkspace";
import { cn, focusRing } from "../lib/cn";
import { formatWhen } from "../lib/format";
import type { FollowupItem } from "../types/workspace";

const sections: { id: FollowupBucket; title: string; empty: string }[] = [
  { id: "overdue", title: "Overdue", empty: "Nothing is overdue." },
  { id: "today", title: "Today", empty: "Nothing is scheduled for today." },
  { id: "upcoming", title: "Upcoming", empty: "Nothing is coming up." },
  { id: "done", title: "Completed", empty: "No completed follow-ups yet." },
];

export function FollowUpsPage() {
  const followups = useFollowups();

  return (
    <>
      <PageHeader
        title="Follow-ups"
        description="Overdue, today, and upcoming check-ins for prospects you have already contacted."
      />
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
        return (
          <Card key={section.id}>
            <div className="flex items-center justify-between gap-3">
              <h2 className="text-h4 font-semibold text-ink">{section.title}</h2>
              <span className="text-caption text-gray-500">{rows.length}</span>
            </div>
            {rows.length === 0 ? (
              <p className="mt-4 text-body text-gray-600">{section.empty}</p>
            ) : (
              <ul className="mt-4 divide-y divide-gray-200">
                {rows.map((item) => (
                  <li key={item.id} className="py-4">
                    <div className="flex flex-col gap-2 sm:flex-row sm:items-start sm:justify-between">
                      <div>
                        <Link
                          to={`/leads/${item.lead_id}`}
                          className={cn("font-semibold text-ink hover:text-primary-700", focusRing)}
                        >
                          {item.business_name}
                        </Link>
                        <p className="mt-1 text-small text-gray-600">
                          {[item.city, typeLabel(item.type), formatWhen(item.scheduled_for)]
                            .filter(Boolean)
                            .join(" · ")}
                        </p>
                      </div>
                      <StatusBadge status={item.status} />
                    </div>
                    {item.notes ? (
                      <p className="mt-2 text-body text-gray-700">{item.notes}</p>
                    ) : null}
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

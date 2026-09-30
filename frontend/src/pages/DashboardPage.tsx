import { RefreshCw } from "lucide-react";
import axios from "axios";
import { Link, useNavigate } from "react-router-dom";

import { Card } from "../components/ui/Card";
import { EmptyState } from "../components/feedback/EmptyState";
import { PageHeader } from "../components/layout/PageHeader";
import { Badge, StatusBadge } from "../components/ui/Badge";
import { Button } from "../components/ui/Button";
import { Skeleton } from "../components/ui/Skeleton";
import { useHealth } from "../hooks/useHealth";
import { useLeads } from "../hooks/useLeads";
import { cn, focusRing } from "../lib/cn";
import { formatWhen } from "../lib/format";
import { isApiErrorBody } from "../types/api";
import type { Lead } from "../types/lead";

const closed = new Set(["WON", "LOST", "NOT_INTERESTED"]);
const viewedAt = new Date().toISOString();

function errorMessage(error: unknown): string {
  if (axios.isAxiosError(error) && isApiErrorBody(error.response?.data)) {
    return error.response.data.error.message;
  }

  return "The API could not be reached.";
}

export function DashboardPage() {
  const health = useHealth();
  const leads = useLeads({ limit: 100, sort: "updated_at", direction: "desc" });
  const navigate = useNavigate();
  const databaseLabel =
    health.data?.database === "ok" ? "Database connected" : "Database unavailable";
  const items = leads.data?.items ?? [];
  const due = items
    .filter((lead) => lead.next_followup_at !== null && lead.next_followup_at <= viewedAt)
    .sort((left, right) =>
      (left.next_followup_at ?? "").localeCompare(right.next_followup_at ?? ""),
    );

  return (
    <>
      <PageHeader
        title="Dashboard"
        description={
          items.length > 0
            ? "What to work on next, based on the leads in this workspace."
            : "What to work on next will collect here as you add leads."
        }
      />
      {leads.isPending ? (
        <div className="mb-6 grid gap-3 sm:grid-cols-2 xl:grid-cols-4" aria-busy="true">
          <Skeleton className="h-24" />
          <Skeleton className="h-24" />
          <Skeleton className="h-24" />
          <Skeleton className="h-24" />
        </div>
      ) : null}
      {leads.isError ? (
        <Card className="mb-6">
          <div className="flex flex-col items-start gap-3" role="alert">
            <p className="text-body text-danger">{errorMessage(leads.error)}</p>
            <Button
              variant="secondary"
              onClick={() => {
                void leads.refetch();
              }}
            >
              <RefreshCw size={16} aria-hidden="true" />
              Retry
            </Button>
          </div>
        </Card>
      ) : null}
      {leads.data && items.length > 0 ? <Summary items={items} dueCount={due.length} /> : null}
      <div className="grid items-start gap-6 lg:grid-cols-[minmax(0,2fr)_320px]">
        {leads.data && items.length === 0 ? (
          <EmptyState
            title="No work queued"
            description="Find local businesses, or add a lead yourself, to start the acquisition workflow."
            action={
              <div className="flex flex-wrap gap-2">
                <Button
                  onClick={() => {
                    navigate("/discover");
                  }}
                >
                  Find leads
                </Button>
                <Button
                  variant="secondary"
                  onClick={() => {
                    navigate("/leads/new");
                  }}
                >
                  Add lead
                </Button>
              </div>
            }
          />
        ) : null}
        {items.length > 0 ? (
          <div className="space-y-6">
            <WorkList title="Follow-ups due" empty="No follow-ups are due." leads={due} />
            <WorkList title="Recently updated" empty="No leads yet." leads={items.slice(0, 6)} />
          </div>
        ) : null}
        <Card>
          <h2 className="text-h4 font-semibold text-ink">System</h2>
          {health.isPending ? (
            <div className="mt-4 space-y-2" aria-busy="true">
              <Skeleton className="h-6 w-40" />
              <Skeleton className="h-4 w-28" />
            </div>
          ) : null}
          {health.isError ? (
            <div className="mt-4 flex flex-col items-start gap-3" role="alert">
              <p className="text-body text-danger">{errorMessage(health.error)}</p>
              <Button
                variant="secondary"
                onClick={() => {
                  void health.refetch();
                }}
              >
                <RefreshCw size={16} aria-hidden="true" />
                Retry
              </Button>
            </div>
          ) : null}
          {health.data ? (
            <div className="mt-4 flex flex-col items-start gap-3">
              <Badge tone={health.data.database === "ok" ? "green" : "orange"}>
                {databaseLabel}
              </Badge>
              <p className="text-small text-gray-500">Environment: {health.data.environment}</p>
            </div>
          ) : null}
        </Card>
      </div>
    </>
  );
}

function Summary({ items, dueCount }: { items: Lead[]; dueCount: number }) {
  const open = items.filter((lead) => !closed.has(lead.lead_status) && lead.lead_status !== "NEW");
  const won = items.filter((lead) => lead.lead_status === "WON").length;
  const stats = [
    { label: "Leads", value: items.length },
    { label: "In progress", value: open.length },
    { label: "Follow-ups due", value: dueCount },
    { label: "Won", value: won },
  ];

  return (
    <div className="mb-6 grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
      {stats.map((stat) => (
        <Card key={stat.label}>
          <p className="text-caption font-semibold text-gray-500">{stat.label}</p>
          <p className="mt-2 text-h2 font-bold text-ink">{stat.value}</p>
        </Card>
      ))}
    </div>
  );
}

function WorkList({ title, empty, leads }: { title: string; empty: string; leads: Lead[] }) {
  return (
    <Card>
      <h2 className="text-h4 font-semibold text-ink">{title}</h2>
      {leads.length === 0 ? <p className="mt-4 text-body text-gray-600">{empty}</p> : null}
      {leads.length > 0 ? (
        <ul className="mt-4 divide-y divide-gray-200">
          {leads.map((lead) => (
            <li
              key={lead.id}
              className="flex flex-col gap-2 py-3 sm:flex-row sm:items-center sm:justify-between"
            >
              <div>
                <Link
                  to={`/leads/${lead.id}`}
                  className={cn("font-medium text-ink hover:text-primary-700", focusRing)}
                >
                  {lead.business_name}
                </Link>
                <p className="text-small text-gray-600">
                  {[lead.city, lead.next_followup_at ? formatWhen(lead.next_followup_at) : null]
                    .filter(Boolean)
                    .join(" · ")}
                </p>
              </div>
              <StatusBadge status={lead.lead_status} />
            </li>
          ))}
        </ul>
      ) : null}
    </Card>
  );
}

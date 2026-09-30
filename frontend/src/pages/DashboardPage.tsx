import { RefreshCw } from "lucide-react";
import axios from "axios";
import { Link, useNavigate } from "react-router-dom";
import {
  Bar,
  BarChart,
  Cell,
  Pie,
  PieChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";

import { EmptyState } from "../components/feedback/EmptyState";
import { PageHeader } from "../components/layout/PageHeader";
import { Badge, StatusBadge } from "../components/ui/Badge";
import { Button } from "../components/ui/Button";
import { Card } from "../components/ui/Card";
import { Skeleton } from "../components/ui/Skeleton";
import { followUpBucket } from "../features/followups/buckets";
import { leadStatusOptions } from "../features/leads/statuses";
import { useHealth } from "../hooks/useHealth";
import { useLeads } from "../hooks/useLeads";
import { useAnalytics, useFollowups } from "../hooks/useWorkspace";
import { cn, focusRing } from "../lib/cn";
import { formatWhen } from "../lib/format";
import { isApiErrorBody } from "../types/api";
import type { HealthResponse } from "../types/health";
import type { Lead } from "../types/lead";
import type { AnalyticsSummary, FollowupItem, LabelCount } from "../types/workspace";

const statusLabel = Object.fromEntries(leadStatusOptions.map((item) => [item.value, item.label]));

const sourceLabels: Record<string, string> = {
  openstreetmap: "OpenStreetMap",
  google_places: "Google Places",
  yelp: "Yelp",
  yell: "Yell",
  businesslist: "BusinessList",
  epages: "ePages",
  csv: "CSV import",
};

const chartColors = ["#4f46e5", "#0f766e", "#b45309", "#1d4ed8", "#6d28d9", "#64748b"];

function errorMessage(error: unknown): string {
  if (axios.isAxiosError(error) && isApiErrorBody(error.response?.data)) {
    return error.response.data.error.message;
  }
  return "The API could not be reached.";
}

function sourceName(value: string): string {
  return (
    sourceLabels[value] ??
    value
      .split("_")
      .map((part) => part.charAt(0).toUpperCase() + part.slice(1))
      .join(" ")
  );
}

function percent(part: number, whole: number): string {
  if (whole <= 0) {
    return "—";
  }
  return `${Math.round((part / whole) * 100)}%`;
}

export function DashboardPage() {
  const navigate = useNavigate();
  const health = useHealth();
  const analytics = useAnalytics();
  const followups = useFollowups();
  const leads = useLeads({ limit: 6, sort: "lead_score", direction: "desc" });
  const due = (followups.data ?? [])
    .filter((item) => {
      const bucket = followUpBucket(item);
      return bucket === "overdue" || bucket === "today";
    })
    .sort((left, right) => left.scheduled_for.localeCompare(right.scheduled_for));

  return (
    <>
      <PageHeader
        title="Dashboard"
        description="What needs attention, where leads come from, and which tools are ready."
        actions={
          <Button
            variant="secondary"
            onClick={() => {
              navigate("/analytics");
            }}
          >
            Full analytics
          </Button>
        }
      />

      {analytics.isPending ? (
        <div className="mb-6 grid gap-3 sm:grid-cols-2 xl:grid-cols-5" aria-busy="true">
          {Array.from({ length: 5 }, (_, index) => (
            <Skeleton key={index} className="h-28" />
          ))}
        </div>
      ) : null}
      {analytics.isError ? (
        <Alert
          message={errorMessage(analytics.error)}
          onRetry={() => {
            void analytics.refetch();
          }}
        />
      ) : null}
      {analytics.data ? <Summary data={analytics.data} dueCount={due.length} /> : null}

      {analytics.isPending ? (
        <div className="mt-6 grid gap-6 xl:grid-cols-2" aria-busy="true">
          <Skeleton className="h-80" />
          <Skeleton className="h-80" />
        </div>
      ) : null}
      {analytics.data ? (
        <div className="mt-6 grid items-start gap-6 xl:grid-cols-2">
          <PipelineChart data={analytics.data} />
          <SourceChart items={analytics.data.by_source ?? []} />
        </div>
      ) : null}

      <section className="mt-6">
        <h2 className="text-h4 font-semibold text-ink">Tools</h2>
        <p className="mt-1 text-small text-gray-600">
          Email drafts use one configured provider. Lead sources are the directories already saved
          in this workspace.
        </p>
        <div className="mt-4 grid gap-3 lg:grid-cols-3">
          <DraftTool
            name="Gemini"
            provider="gemini"
            health={health.data}
            pending={health.isPending}
            readyDetail="Free-tier drafts. Google can use that content to improve its products."
            missingDetail="Add GEMINI_API_KEY in the server environment, then restart the API."
          />
          <DraftTool
            name="Groq"
            provider="groq"
            health={health.data}
            pending={health.isPending}
            readyDetail="Drafts use the Groq API with the business details and audit findings."
            missingDetail="Add GROQ_API_KEY in the server environment, then restart the API."
          />
          <WorkspaceHealth
            health={health.data}
            pending={health.isPending}
            error={health.isError ? errorMessage(health.error) : null}
            onRetry={() => {
              void health.refetch();
            }}
          />
        </div>
      </section>

      {analytics.data ? <Funnel data={analytics.data} /> : null}

      <div className="mt-6 grid items-start gap-6 lg:grid-cols-[minmax(0,1.1fr)_minmax(0,0.9fr)]">
        <FollowUpList items={due.slice(0, 6)} pending={followups.isPending} total={due.length} />
        <StrongLeads
          items={leads.data?.items ?? []}
          pending={leads.isPending}
          error={leads.isError ? errorMessage(leads.error) : null}
          onRetry={() => {
            void leads.refetch();
          }}
        />
      </div>

      {analytics.data ? (
        <div className="mt-6 grid items-start gap-6 lg:grid-cols-2">
          <RankList title="Industries" items={analytics.data.by_industry.slice(0, 6)} />
          <RankList title="Cities" items={analytics.data.by_city.slice(0, 6)} />
        </div>
      ) : null}
    </>
  );
}

function Summary({ data, dueCount }: { data: AnalyticsSummary; dueCount: number }) {
  const stats = [
    {
      label: "Leads",
      value: String(data.leads),
      detail: `${data.audits_completed} audited`,
    },
    {
      label: "Score 70+",
      value: String(data.high_scores ?? 0),
      detail: "Strongest fits to pitch",
    },
    {
      label: "No website",
      value: String(data.websites_missing ?? 0),
      detail: "Openings for a new site",
    },
    {
      label: "Follow-ups due",
      value: String(dueCount),
      detail: dueCount > 0 ? "Overdue or due today" : "Nothing due today",
    },
    {
      label: "Reply rate",
      value: percent(data.replies, data.contacted),
      detail: `${data.replies} ${data.replies === 1 ? "reply" : "replies"} from ${data.contacted} contacted`,
    },
  ];

  return (
    <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-5">
      {stats.map((stat) => (
        <Card key={stat.label} className="shadow-sm">
          <p className="text-caption font-semibold text-gray-500">{stat.label}</p>
          <p className="mt-2 text-h2 font-bold text-ink tabular-nums">{stat.value}</p>
          <p className="mt-1 text-caption text-gray-500">{stat.detail}</p>
        </Card>
      ))}
    </div>
  );
}

function PipelineChart({ data }: { data: AnalyticsSummary | undefined }) {
  const rows = (data?.by_status ?? [])
    .filter((item) => item.count > 0)
    .map((item) => ({
      label: statusLabel[item.status] ?? item.status,
      count: item.count,
    }));

  return (
    <Card className="shadow-sm">
      <h2 className="text-h4 font-semibold text-ink">Pipeline</h2>
      <p className="mt-1 text-small text-gray-600">Leads in each stage.</p>
      {rows.length === 0 ? (
        <p className="mt-6 text-body text-gray-600">No leads in the pipeline yet.</p>
      ) : (
        <div className="mt-4" style={{ height: Math.max(220, rows.length * 36) }}>
          <ResponsiveContainer width="100%" height="100%">
            <BarChart
              data={rows}
              layout="vertical"
              margin={{ left: 8, right: 8, top: 0, bottom: 0 }}
            >
              <XAxis type="number" allowDecimals={false} tick={{ fontSize: 12 }} />
              <YAxis type="category" dataKey="label" width={110} tick={{ fontSize: 12 }} />
              <Tooltip />
              <Bar dataKey="count" fill="#4f46e5" radius={4} />
            </BarChart>
          </ResponsiveContainer>
        </div>
      )}
    </Card>
  );
}

function SourceChart({ items }: { items: LabelCount[] }) {
  const rows = items.map((item) => ({
    label: sourceName(item.label),
    count: item.count,
  }));
  const total = rows.reduce((sum, item) => sum + item.count, 0);

  return (
    <Card className="shadow-sm">
      <h2 className="text-h4 font-semibold text-ink">Lead sources</h2>
      <p className="mt-1 text-small text-gray-600">Directories and imports already saved.</p>
      {rows.length === 0 ? (
        <p className="mt-6 text-body text-gray-600">No sourced leads yet.</p>
      ) : (
        <div className="mt-4 grid items-center gap-4 sm:grid-cols-[180px_minmax(0,1fr)]">
          <div className="h-44">
            <ResponsiveContainer width="100%" height="100%">
              <PieChart>
                <Pie data={rows} dataKey="count" nameKey="label" innerRadius={48} outerRadius={72}>
                  {rows.map((row, index) => (
                    <Cell key={row.label} fill={chartColors[index % chartColors.length]} />
                  ))}
                </Pie>
                <Tooltip />
              </PieChart>
            </ResponsiveContainer>
          </div>
          <ul className="space-y-2">
            {rows.map((row, index) => (
              <li key={row.label} className="flex items-center justify-between gap-3 text-body">
                <span className="flex min-w-0 items-center gap-2 text-ink">
                  <span
                    className="size-2.5 shrink-0 rounded-full"
                    style={{ backgroundColor: chartColors[index % chartColors.length] }}
                    aria-hidden="true"
                  />
                  <span className="truncate">{row.label}</span>
                </span>
                <span className="font-medium tabular-nums text-gray-600">
                  {row.count}
                  <span className="ml-2 text-caption text-gray-500">
                    · {percent(row.count, total)}
                  </span>
                </span>
              </li>
            ))}
          </ul>
        </div>
      )}
    </Card>
  );
}

function DraftTool({
  name,
  provider,
  health,
  pending,
  readyDetail,
  missingDetail,
}: {
  name: string;
  provider: "gemini" | "groq";
  health: HealthResponse | undefined;
  pending: boolean;
  readyDetail: string;
  missingDetail: string;
}) {
  const state = health?.[provider];
  const active = health?.email_drafts === provider;
  const detail =
    state === "missing"
      ? missingDetail
      : active
        ? readyDetail
        : state === "ready"
          ? "Configured. Switch the provider in the server environment to use it for drafts."
          : readyDetail;

  return (
    <Card className={cn("shadow-sm", active && "border-primary-200")}>
      <div className="flex items-start justify-between gap-3">
        <h3 className="text-h4 font-semibold text-ink">{name}</h3>
        {pending ? <Skeleton className="h-6 w-16" /> : null}
        {!pending && state ? (
          <Badge tone={state === "ready" ? "green" : "orange"}>
            {state === "ready" ? "Ready" : "Not configured"}
          </Badge>
        ) : null}
        {!pending && !state && health ? (
          <Badge tone={active ? "green" : "gray"}>{active ? "Active" : "Standby"}</Badge>
        ) : null}
      </div>
      {active ? (
        <p className="mt-3 text-caption font-semibold text-primary-700">Used for email drafts</p>
      ) : null}
      <p className="mt-2 text-small text-gray-600">{detail}</p>
    </Card>
  );
}

function WorkspaceHealth({
  health,
  pending,
  error,
  onRetry,
}: {
  health: HealthResponse | undefined;
  pending: boolean;
  error: string | null;
  onRetry: () => void;
}) {
  return (
    <Card className="shadow-sm">
      <h3 className="text-h4 font-semibold text-ink">Workspace</h3>
      {pending ? (
        <div className="mt-4 space-y-2" aria-busy="true">
          <Skeleton className="h-6 w-40" />
          <Skeleton className="h-4 w-28" />
        </div>
      ) : null}
      {error ? (
        <div className="mt-4 flex flex-col items-start gap-3" role="alert">
          <p className="text-body text-danger">{error}</p>
          <Button variant="secondary" onClick={onRetry}>
            <RefreshCw size={16} aria-hidden="true" />
            Retry
          </Button>
        </div>
      ) : null}
      {health ? (
        <dl className="mt-4 space-y-3">
          <div className="flex items-center justify-between gap-3">
            <dt className="text-small text-gray-600">Database</dt>
            <dd>
              <Badge tone={health.database === "ok" ? "green" : "orange"}>
                {health.database === "ok" ? "Connected" : "Unavailable"}
              </Badge>
            </dd>
          </div>
          <div className="flex items-center justify-between gap-3">
            <dt className="text-small text-gray-600">Environment</dt>
            <dd className="text-small font-medium text-ink">{health.environment}</dd>
          </div>
        </dl>
      ) : null}
    </Card>
  );
}

function Funnel({ data }: { data: AnalyticsSummary }) {
  const steps = [
    { label: "Leads", value: data.leads },
    { label: "Audits", value: data.audits_completed },
    { label: "Mockups", value: data.mockups_ready },
    { label: "Contacted", value: data.contacted },
    { label: "Replies", value: data.replies },
    { label: "Wins", value: data.wins },
  ];
  const max = Math.max(data.leads, 1);

  return (
    <Card className="mt-6 shadow-sm">
      <h2 className="text-h4 font-semibold text-ink">Acquisition</h2>
      <p className="mt-1 text-small text-gray-600">
        {data.wins} {data.wins === 1 ? "win" : "wins"} from {data.contacted} contacted.{" "}
        {percent(data.wins, data.contacted)} of contacted leads are won.
      </p>
      <ol className="mt-4 grid gap-3 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-6">
        {steps.map((step) => (
          <li key={step.label}>
            <p className="text-caption font-semibold text-gray-500">{step.label}</p>
            <p className="mt-1 text-h4 font-semibold text-ink tabular-nums">{step.value}</p>
            <div className="mt-2 h-1.5 overflow-hidden rounded-full bg-gray-100">
              <div
                className="h-full rounded-full bg-primary"
                style={{ width: `${Math.round((step.value / max) * 100)}%` }}
              />
            </div>
          </li>
        ))}
      </ol>
    </Card>
  );
}

function FollowUpList({
  items,
  pending,
  total,
}: {
  items: FollowupItem[];
  pending: boolean;
  total: number;
}) {
  return (
    <Card className="shadow-sm">
      <div className="flex items-baseline justify-between gap-3">
        <h2 className="text-h4 font-semibold text-ink">Follow-ups due</h2>
        <Link
          to="/follow-ups"
          className={cn("text-small font-semibold text-primary-700", focusRing)}
        >
          All follow-ups
        </Link>
      </div>
      {pending ? (
        <div className="mt-4 space-y-3" aria-busy="true">
          <Skeleton className="h-12" />
          <Skeleton className="h-12" />
        </div>
      ) : null}
      {!pending && items.length === 0 ? (
        <p className="mt-4 text-body text-gray-600">Nothing is overdue or due today.</p>
      ) : null}
      {items.length > 0 ? (
        <ul className="mt-2 divide-y divide-gray-100">
          {items.map((item) => (
            <li key={item.id} className="flex items-center justify-between gap-3 py-3">
              <div className="min-w-0">
                <Link
                  to={`/leads/${item.lead_id}`}
                  className={cn("font-medium text-ink hover:text-primary-700", focusRing)}
                >
                  {item.business_name}
                </Link>
                <p className="text-small text-gray-600">
                  {[item.city, formatWhen(item.scheduled_for)].filter(Boolean).join(" · ")}
                </p>
              </div>
              <StatusBadge status={followUpBucket(item) === "overdue" ? "DUE" : item.status} />
            </li>
          ))}
        </ul>
      ) : null}
      {total > items.length ? (
        <p className="mt-2 text-caption text-gray-500">{total - items.length} more due.</p>
      ) : null}
    </Card>
  );
}

function StrongLeads({
  items,
  pending,
  error,
  onRetry,
}: {
  items: Lead[];
  pending: boolean;
  error: string | null;
  onRetry: () => void;
}) {
  return (
    <Card className="shadow-sm">
      <div className="flex items-baseline justify-between gap-3">
        <h2 className="text-h4 font-semibold text-ink">Highest scores</h2>
        <Link to="/leads" className={cn("text-small font-semibold text-primary-700", focusRing)}>
          All leads
        </Link>
      </div>
      {pending ? (
        <div className="mt-4 space-y-3" aria-busy="true">
          <Skeleton className="h-12" />
          <Skeleton className="h-12" />
        </div>
      ) : null}
      {error ? (
        <div className="mt-4" role="alert">
          <p className="text-body text-danger">{error}</p>
          <Button className="mt-3" variant="secondary" onClick={onRetry}>
            Retry
          </Button>
        </div>
      ) : null}
      {!pending && !error && items.length === 0 ? (
        <EmptyState
          title="No leads yet"
          description="Find local businesses, or add a lead yourself."
          action={
            <Link
              to="/discover"
              className={cn("text-body font-semibold text-primary-700", focusRing)}
            >
              Find leads
            </Link>
          }
        />
      ) : null}
      {items.length > 0 ? (
        <ul className="mt-2 divide-y divide-gray-100">
          {items.map((lead) => (
            <li key={lead.id} className="flex items-center justify-between gap-3 py-3">
              <div className="min-w-0">
                <Link
                  to={`/leads/${lead.id}`}
                  className={cn("font-medium text-ink hover:text-primary-700", focusRing)}
                >
                  {lead.business_name}
                </Link>
                <p className="truncate text-small text-gray-600">
                  {[lead.industry, lead.source ? sourceName(lead.source) : null]
                    .filter(Boolean)
                    .join(" · ") || "—"}
                </p>
              </div>
              <span className="text-h4 font-semibold text-ink tabular-nums">
                {lead.lead_score ?? "—"}
              </span>
            </li>
          ))}
        </ul>
      ) : null}
    </Card>
  );
}

function RankList({ title, items }: { title: string; items: LabelCount[] }) {
  const max = Math.max(...items.map((item) => item.count), 1);

  return (
    <Card className="shadow-sm">
      <h2 className="text-h4 font-semibold text-ink">{title}</h2>
      {items.length === 0 ? <p className="mt-4 text-body text-gray-600">No data yet.</p> : null}
      {items.length > 0 ? (
        <ul className="mt-4 space-y-3">
          {items.map((item) => (
            <li key={item.label}>
              <div className="flex items-baseline justify-between gap-3 text-body text-ink">
                <span className="truncate">{item.label}</span>
                <span className="font-medium tabular-nums">{item.count}</span>
              </div>
              <div className="mt-1.5 h-1.5 overflow-hidden rounded-full bg-gray-100">
                <div
                  className="h-full rounded-full bg-primary"
                  style={{ width: `${Math.round((item.count / max) * 100)}%` }}
                />
              </div>
            </li>
          ))}
        </ul>
      ) : null}
    </Card>
  );
}

function Alert({ message, onRetry }: { message: string; onRetry: () => void }) {
  return (
    <Card className="mb-6">
      <div className="flex flex-col items-start gap-3" role="alert">
        <p className="text-body text-danger">{message}</p>
        <Button variant="secondary" onClick={onRetry}>
          <RefreshCw size={16} aria-hidden="true" />
          Retry
        </Button>
      </div>
    </Card>
  );
}

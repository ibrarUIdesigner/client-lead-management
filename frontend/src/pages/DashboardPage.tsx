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

import { PageHeader } from "../components/layout/PageHeader";
import { Badge, StatusBadge } from "../components/ui/Badge";
import { Button } from "../components/ui/Button";
import { Card } from "../components/ui/Card";
import { Skeleton } from "../components/ui/Skeleton";
import { followUpBucket } from "../features/followups/buckets";
import { leadStatusOptions } from "../features/leads/statuses";
import { useHealth, useProviders } from "../hooks/useHealth";
import { useAnalytics, useFollowups } from "../hooks/useWorkspace";
import { cn, focusRing } from "../lib/cn";
import { formatWhen } from "../lib/format";
import { isApiErrorBody } from "../types/api";
import type { HealthResponse, ProviderSnapshot } from "../types/health";
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

const providerNames: Record<ProviderSnapshot["id"], string> = {
  gemini: "Gemini",
  groq: "Groq",
};

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

function formatTokens(value: number): string {
  return new Intl.NumberFormat("en-US").format(value);
}

function formatUsd(value: number): string {
  return new Intl.NumberFormat("en-US", {
    style: "currency",
    currency: "USD",
    minimumFractionDigits: 2,
    maximumFractionDigits: 4,
  }).format(value);
}

export function DashboardPage() {
  const navigate = useNavigate();
  const health = useHealth();
  const providers = useProviders();
  const analytics = useAnalytics();
  const followups = useFollowups();
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
        <div className="mt-6 grid gap-6 xl:grid-cols-2">
          <PipelineChart data={analytics.data} />
          <SourceChart items={analytics.data.by_source ?? []} />
        </div>
      ) : null}

      <section className="mt-6">
        <h2 className="text-h4 font-semibold text-ink">Tools</h2>
        <p className="mt-1 text-small text-gray-600">
          Model limits come from each provider’s catalog. Credit balances are not exposed by
          either API.
        </p>
        <div className="mt-4 grid gap-3 lg:grid-cols-2">
          <ProviderCard
            id="gemini"
            snapshot={providers.data?.providers.find((item) => item.id === "gemini")}
            pending={providers.isPending}
            health={health.data}
            drafts={analytics.data?.outreach_drafts ?? null}
          />
          <ProviderCard
            id="groq"
            snapshot={providers.data?.providers.find((item) => item.id === "groq")}
            pending={providers.isPending}
            health={health.data}
            drafts={analytics.data?.outreach_drafts ?? null}
          />
        </div>
        {providers.isError ? (
          <p className="mt-3 text-small text-gray-600" role="status">
            Provider limits could not be loaded. Status still comes from the workspace health
            check.
          </p>
        ) : null}
        <WorkspaceLine
          health={health.data}
          pending={health.isPending}
          error={health.isError ? errorMessage(health.error) : null}
          onRetry={() => {
            void health.refetch();
          }}
        />
      </section>

      {analytics.data ? <Funnel data={analytics.data} /> : null}

      {due.length > 0 ? (
        <div className="mt-6">
          <FollowUpList items={due.slice(0, 5)} total={due.length} />
        </div>
      ) : null}

      {analytics.data && analytics.data.by_city.length > 0 ? (
        <CityMix data={analytics.data} />
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
    <Card className="flex h-full flex-col shadow-sm">
      <h2 className="text-h4 font-semibold text-ink">Pipeline</h2>
      <p className="mt-1 text-small text-gray-600">Leads in each stage.</p>
      {rows.length === 0 ? (
        <p className="mt-6 flex-1 text-body text-gray-600">No leads in the pipeline yet.</p>
      ) : (
        <div className="mt-4 min-h-72 flex-1">
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
    <Card className="flex h-full flex-col shadow-sm">
      <h2 className="text-h4 font-semibold text-ink">Lead sources</h2>
      <p className="mt-1 text-small text-gray-600">Directories and imports already saved.</p>
      {rows.length === 0 ? (
        <p className="mt-6 flex-1 text-body text-gray-600">No sourced leads yet.</p>
      ) : (
        <div className="mt-4 grid min-h-72 flex-1 items-center gap-4 sm:grid-cols-[180px_minmax(0,1fr)]">
          <div className="h-44 sm:h-full">
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
                <span className="shrink-0 font-medium tabular-nums text-gray-600">
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

function ProviderCard({
  id,
  snapshot,
  pending,
  health,
  drafts,
}: {
  id: ProviderSnapshot["id"];
  snapshot: ProviderSnapshot | undefined;
  pending: boolean;
  health: HealthResponse | undefined;
  drafts: number | null;
}) {
  const active = snapshot?.active ?? health?.email_drafts === id;
  const configured = snapshot
    ? snapshot.configured
    : health
      ? health[id] === "ready" || health.email_drafts === id
      : undefined;

  return (
    <Card className={cn("flex h-full flex-col shadow-sm", active && "ring-2 ring-primary-200")}>
      <div className="flex items-start justify-between gap-3">
        <h3 className="text-h4 font-semibold text-ink">{providerNames[id]}</h3>
        {pending && !snapshot ? <Skeleton className="h-6 w-24" /> : null}
        {snapshot || health ? (
          <Badge tone={!snapshot && !health ? "gray" : configured === false ? "orange" : "green"}>
            {configured === false ? "Not configured" : active ? "Active" : "Ready"}
          </Badge>
        ) : null}
      </div>
      {active ? (
        <p className="mt-3 text-caption font-semibold text-primary-700">Used for email drafts</p>
      ) : null}
      {pending && !snapshot ? (
        <div className="mt-4 space-y-2" aria-busy="true">
          <Skeleton className="h-4 w-40" />
          <Skeleton className="h-4 w-56" />
          <Skeleton className="h-16" />
        </div>
      ) : (
        <ProviderFacts snapshot={snapshot} drafts={drafts} active={Boolean(active)} />
      )}
    </Card>
  );
}

function ProviderFacts({
  snapshot,
  drafts,
  active,
}: {
  snapshot: ProviderSnapshot | undefined;
  drafts: number | null;
  active: boolean;
}) {
  if (!snapshot) {
    return (
      <p className="mt-3 text-small text-gray-600">
        {active
          ? "This provider is selected for drafts. Model limits will appear when the catalog responds."
          : "Standing by. Model limits appear when the catalog responds."}
      </p>
    );
  }

  const title = snapshot.display_name ?? snapshot.model;
  const prices = [
    snapshot.prompt_usd_per_million != null
      ? `${formatUsd(snapshot.prompt_usd_per_million)} / 1M input`
      : null,
    snapshot.completion_usd_per_million != null
      ? `${formatUsd(snapshot.completion_usd_per_million)} / 1M output`
      : null,
  ].filter((item): item is string => item != null);

  return (
    <dl className="mt-4 flex flex-1 flex-col gap-4">
      <div>
        <dt className="text-caption font-semibold text-gray-500">Model</dt>
        <dd className="mt-1 text-body font-medium text-ink">{title}</dd>
        {snapshot.display_name ? (
          <dd className="text-caption text-gray-500">{snapshot.model}</dd>
        ) : null}
        {snapshot.listed === false ? (
          <dd className="mt-1 text-small text-amber-800">
            This model is not in the current catalog. Drafts that use it may fail.
          </dd>
        ) : null}
      </div>
      {snapshot.input_tokens || snapshot.output_tokens ? (
        <div>
          <dt className="text-caption font-semibold text-gray-500">Capacity</dt>
          <dd className="mt-1 text-body text-ink">
            {snapshot.input_tokens
              ? `${formatTokens(snapshot.input_tokens)} input tokens`
              : "Input limit not listed"}
          </dd>
          <dd className="text-small text-gray-600">
            {snapshot.output_tokens
              ? `${formatTokens(snapshot.output_tokens)} output tokens`
              : "Output limit not listed"}
          </dd>
        </div>
      ) : null}
      {prices.length > 0 ? (
        <div>
          <dt className="text-caption font-semibold text-gray-500">Price</dt>
          {prices.map((price) => (
            <dd key={price} className="mt-1 text-body text-ink">
              {price}
            </dd>
          ))}
        </div>
      ) : null}
      <div>
        <dt className="text-caption font-semibold text-gray-500">Credits</dt>
        <dd className="mt-1 text-small text-gray-600">{snapshot.credits}</dd>
      </div>
      <div className="mt-auto border-t border-gray-100 pt-4">
        <dt className="text-caption font-semibold text-gray-500">Usage in this workspace</dt>
        <dd className="mt-1 text-body text-ink">
          {active
            ? drafts == null
              ? "Draft count is still loading."
              : `${drafts} ${drafts === 1 ? "draft" : "drafts"} saved`
            : "Not writing drafts. Saved drafts stay on the active provider."}
        </dd>
        <dd className="text-caption text-gray-500">
          {active
            ? "Past token totals are not stored, so usage here is drafts only."
            : "Switch the provider in the server environment to use this model."}
        </dd>
      </div>
    </dl>
  );
}

function WorkspaceLine({
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
  if (pending) {
    return <Skeleton className="mt-3 h-6 w-64" />;
  }
  if (error) {
    return (
      <div className="mt-3 flex items-center gap-3" role="alert">
        <p className="text-small text-danger">{error}</p>
        <Button variant="secondary" onClick={onRetry}>
          <RefreshCw size={16} aria-hidden="true" />
          Retry
        </Button>
      </div>
    );
  }
  if (!health) {
    return null;
  }
  return (
    <p className="mt-3 text-small text-gray-600">
      Database {health.database === "ok" ? "connected" : "unavailable"} · {health.environment}
    </p>
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

function FollowUpList({ items, total }: { items: FollowupItem[]; total: number }) {
  return (
    <Card className="shadow-sm">
      <div className="flex items-baseline justify-between gap-3">
        <h2 className="text-h4 font-semibold text-ink">Follow-ups due</h2>
        <Link to="/follow-ups" className={cn("text-small font-semibold text-primary-700", focusRing)}>
          All follow-ups
        </Link>
      </div>
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
      {total > items.length ? (
        <p className="mt-2 text-caption text-gray-500">{total - items.length} more due.</p>
      ) : null}
    </Card>
  );
}

function CityMix({ data }: { data: AnalyticsSummary }) {
  const rows = data.by_city.slice(0, 6);
  const total = data.leads || rows.reduce((sum, item) => sum + item.count, 0);
  const topIndustry = data.by_industry[0];
  const industryShare = topIndustry && data.leads > 0 ? topIndustry.count / data.leads : 0;

  return (
    <Card className="mt-6 shadow-sm">
      <h2 className="text-h4 font-semibold text-ink">Where leads are</h2>
      <p className="mt-1 text-small text-gray-600">
        {industryShare >= 0.8 && topIndustry
          ? `Most of the book is one industry, ${topIndustry.label} (${topIndustry.count} of ${data.leads}). Cities are the split that changes who you call.`
          : "City mix across the leads already saved."}
      </p>
      <ul className="mt-4 space-y-3">
        {rows.map((item) => (
          <li key={item.label}>
            <div className="flex items-baseline justify-between gap-3 text-body text-ink">
              <span className="truncate">{item.label}</span>
              <span className="shrink-0 font-medium tabular-nums">
                {item.count}
                <span className="ml-2 text-caption font-normal text-gray-500">
                  · {percent(item.count, total)}
                </span>
              </span>
            </div>
            <div className="mt-1.5 h-1.5 overflow-hidden rounded-full bg-gray-100">
              <div
                className="h-full rounded-full bg-primary"
                style={{ width: `${Math.round((item.count / Math.max(total, 1)) * 100)}%` }}
              />
            </div>
          </li>
        ))}
      </ul>
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

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

import { QueryGate } from "../components/feedback/QueryGate";
import { PageHeader } from "../components/layout/PageHeader";
import { Card } from "../components/ui/Card";
import { leadStatusOptions } from "../features/leads/statuses";
import { useAnalytics } from "../hooks/useWorkspace";
import type { AnalyticsSummary, LabelCount } from "../types/workspace";

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

export function AnalyticsPage() {
  const analytics = useAnalytics();

  return (
    <>
      <PageHeader
        title="Analytics"
        description="How this workspace is filling, where the leads come from, and what converts."
      />
      <QueryGate
        pending={analytics.isPending}
        error={analytics.error}
        onRetry={() => {
          void analytics.refetch();
        }}
        fallback="Analytics could not be loaded."
      >
        {analytics.data ? <AnalyticsBody data={analytics.data} /> : null}
      </QueryGate>
    </>
  );
}

function AnalyticsBody({ data }: { data: AnalyticsSummary }) {
  const high = data.high_scores ?? 0;
  const missing = data.websites_missing ?? 0;
  const drafts = data.outreach_drafts ?? 0;

  return (
    <div className="space-y-6">
      <Card className="shadow-sm">
        <p className="text-body text-ink">
          {data.leads} {data.leads === 1 ? "lead" : "leads"} in the book. {percent(high, data.leads)}{" "}
          score 70 or higher, and {percent(missing, data.leads)} have no website.{" "}
          {percent(data.replies, data.contacted)} of contacted leads have replied.
        </p>
      </Card>

      <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
        <RateCard
          label="Strong fits"
          value={percent(high, data.leads)}
          detail={`${high} of ${data.leads} score 70+`}
        />
        <RateCard
          label="No website"
          value={percent(missing, data.leads)}
          detail={`${missing} openings for a new site`}
        />
        <RateCard
          label="Audited"
          value={percent(data.audits_completed, data.leads)}
          detail={`${data.audits_completed} audits completed`}
        />
        <RateCard
          label="Reply rate"
          value={percent(data.replies, data.contacted)}
          detail={`${data.replies} ${data.replies === 1 ? "reply" : "replies"} from ${data.contacted} contacted`}
        />
      </div>

      <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-6">
        <MiniStat label="Meetings" value={data.meetings} />
        <MiniStat label="Proposals" value={data.proposals} />
        <MiniStat label="Wins" value={data.wins} />
        <MiniStat label="Losses" value={data.losses} />
        <MiniStat label="Mockups" value={data.mockups_ready} />
        <MiniStat label="Drafts" value={drafts} />
      </div>

      <div className="grid gap-6 xl:grid-cols-2">
        <PipelineChart data={data} />
        <SourceChart items={data.by_source ?? []} />
      </div>

      <Card className="shadow-sm">
        <h2 className="text-h4 font-semibold text-ink">Acquisition</h2>
        <p className="mt-1 text-small text-gray-600">
          Each step is a share of all leads, so a later step can be larger than the one before it
          when work skipped ahead.
        </p>
        <Funnel data={data} />
      </Card>

      <div className="grid gap-6 xl:grid-cols-2">
        <ShareChart title="Cities" hint="Where the saved leads sit." items={data.by_city} total={data.leads} />
        <ShareChart
          title="Industries"
          hint="Useful when the book is mixed. A single dominant industry means city and score matter more."
          items={data.by_industry}
          total={data.leads}
        />
      </div>
    </div>
  );
}

function RateCard({ label, value, detail }: { label: string; value: string; detail: string }) {
  return (
    <Card className="shadow-sm">
      <p className="text-caption font-semibold text-gray-500">{label}</p>
      <p className="mt-2 text-h2 font-bold text-ink tabular-nums">{value}</p>
      <p className="mt-1 text-caption text-gray-500">{detail}</p>
    </Card>
  );
}

function MiniStat({ label, value }: { label: string; value: number }) {
  return (
    <Card className="shadow-sm">
      <p className="text-caption font-semibold text-gray-500">{label}</p>
      <p className="mt-2 text-h3 font-semibold text-ink tabular-nums">{value}</p>
    </Card>
  );
}

function PipelineChart({ data }: { data: AnalyticsSummary }) {
  const rows = data.by_status
    .filter((item) => item.count > 0)
    .map((item) => ({
      label: statusLabel[item.status] ?? item.status,
      count: item.count,
    }));
  const quiet = data.by_status.filter((item) => item.count === 0).length;

  return (
    <Card className="flex h-full flex-col shadow-sm">
      <h2 className="text-h4 font-semibold text-ink">Pipeline</h2>
      <p className="mt-1 text-small text-gray-600">
        Stages that already have leads.
        {quiet > 0 ? ` ${quiet} ${quiet === 1 ? "stage is" : "stages are"} still empty.` : ""}
      </p>
      {rows.length === 0 ? (
        <p className="mt-6 flex-1 text-body text-gray-600">No leads in the pipeline yet.</p>
      ) : (
        <div className="mt-4 min-h-80 flex-1">
          <ResponsiveContainer width="100%" height="100%">
            <BarChart data={rows} layout="vertical" margin={{ left: 8, right: 8, top: 0, bottom: 0 }}>
              <XAxis type="number" allowDecimals={false} tick={{ fontSize: 12 }} />
              <YAxis type="category" dataKey="label" width={120} tick={{ fontSize: 12 }} />
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
      <p className="mt-1 text-small text-gray-600">Share of sourced leads, not every empty directory.</p>
      {rows.length === 0 ? (
        <p className="mt-6 flex-1 text-body text-gray-600">No sourced leads yet.</p>
      ) : (
        <div className="mt-4 grid min-h-80 flex-1 items-center gap-4 sm:grid-cols-[200px_minmax(0,1fr)]">
          <div className="h-48 sm:h-full">
            <ResponsiveContainer width="100%" height="100%">
              <PieChart>
                <Pie data={rows} dataKey="count" nameKey="label" innerRadius={52} outerRadius={78}>
                  {rows.map((row, index) => (
                    <Cell key={row.label} fill={chartColors[index % chartColors.length]} />
                  ))}
                </Pie>
                <Tooltip />
              </PieChart>
            </ResponsiveContainer>
          </div>
          <ul className="space-y-3">
            {rows.map((row, index) => (
              <li key={row.label}>
                <div className="flex items-center justify-between gap-3 text-body">
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
                    <span className="ml-2 text-caption text-gray-500">· {percent(row.count, total)}</span>
                  </span>
                </div>
                <div className="mt-1.5 h-1.5 overflow-hidden rounded-full bg-gray-100">
                  <div
                    className="h-full rounded-full"
                    style={{
                      width: `${Math.round((row.count / Math.max(total, 1)) * 100)}%`,
                      backgroundColor: chartColors[index % chartColors.length],
                    }}
                  />
                </div>
              </li>
            ))}
          </ul>
        </div>
      )}
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
    { label: "Meetings", value: data.meetings },
    { label: "Proposals", value: data.proposals },
    { label: "Wins", value: data.wins },
  ];
  const max = Math.max(data.leads, 1);

  return (
    <ol className="mt-4 grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
      {steps.map((step) => (
        <li key={step.label} className="rounded-control border border-gray-100 px-3 py-3">
          <div className="flex items-baseline justify-between gap-3">
            <p className="text-caption font-semibold text-gray-500">{step.label}</p>
            <p className="text-caption tabular-nums text-gray-500">{percent(step.value, data.leads)}</p>
          </div>
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
  );
}

function ShareChart({
  title,
  hint,
  items,
  total,
}: {
  title: string;
  hint: string;
  items: LabelCount[];
  total: number;
}) {
  const rows = items.slice(0, 8).map((item) => ({ label: item.label, count: item.count }));
  const height = Math.max(220, rows.length * 36);

  return (
    <Card className="flex h-full flex-col shadow-sm">
      <h2 className="text-h4 font-semibold text-ink">{title}</h2>
      <p className="mt-1 text-small text-gray-600">{hint}</p>
      {rows.length === 0 ? (
        <p className="mt-6 flex-1 text-body text-gray-600">No data yet.</p>
      ) : (
        <div className="mt-4 flex-1" style={{ minHeight: height }}>
          <ResponsiveContainer width="100%" height="100%">
            <BarChart data={rows} layout="vertical" margin={{ left: 8, right: 16, top: 0, bottom: 0 }}>
              <XAxis type="number" allowDecimals={false} tick={{ fontSize: 12 }} />
              <YAxis type="category" dataKey="label" width={110} tick={{ fontSize: 12 }} />
              <Tooltip
                formatter={(value) => {
                  const count = typeof value === "number" ? value : 0;
                  return [`${count} · ${percent(count, total)}`, title];
                }}
              />
              <Bar dataKey="count" fill="#4f46e5" radius={4} />
            </BarChart>
          </ResponsiveContainer>
        </div>
      )}
    </Card>
  );
}

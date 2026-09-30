import { Bar, BarChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";

import { QueryGate } from "../components/feedback/QueryGate";
import { PageHeader } from "../components/layout/PageHeader";
import { Card } from "../components/ui/Card";
import { useAnalytics } from "../hooks/useWorkspace";
import { leadStatusOptions } from "../features/leads/statuses";
import type { AnalyticsSummary, LabelCount } from "../types/workspace";

const statusLabel = Object.fromEntries(leadStatusOptions.map((item) => [item.value, item.label]));

export function AnalyticsPage() {
  const analytics = useAnalytics();

  return (
    <>
      <PageHeader
        title="Analytics"
        description="How acquisition work is moving through this workspace."
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
  const stats = [
    { label: "Leads", value: data.leads },
    { label: "Audits completed", value: data.audits_completed },
    { label: "Mockups ready", value: data.mockups_ready },
    { label: "Contacted", value: data.contacted },
    { label: "Replies", value: data.replies },
    { label: "Meetings", value: data.meetings },
    { label: "Proposals", value: data.proposals },
    { label: "Wins", value: data.wins },
    { label: "Losses", value: data.losses },
  ];
  const pipeline = data.by_status.map((item) => ({
    label: statusLabel[item.status] ?? item.status,
    count: item.count,
  }));

  return (
    <div className="space-y-6">
      <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-3">
        {stats.map((stat) => (
          <Card key={stat.label}>
            <p className="text-caption font-semibold text-gray-500">{stat.label}</p>
            <p className="mt-2 text-h2 font-bold text-ink">{stat.value}</p>
          </Card>
        ))}
      </div>
      <p className="text-body text-gray-700">
        {data.wins} {data.wins === 1 ? "win" : "wins"} from {data.contacted} contacted{" "}
        {data.contacted === 1 ? "note" : "notes"}.
      </p>
      <div className="grid items-start gap-6 xl:grid-cols-[minmax(0,3fr)_minmax(280px,1fr)]">
        <Card>
          <h2 className="text-h4 font-semibold text-ink">Pipeline</h2>
          <div className="mt-4 h-[28rem]">
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={pipeline} layout="vertical" margin={{ left: 16, right: 8 }}>
                <XAxis type="number" allowDecimals={false} />
                <YAxis type="category" dataKey="label" width={120} tick={{ fontSize: 12 }} />
                <Tooltip />
                <Bar dataKey="count" fill="#4f46e5" radius={4} />
              </BarChart>
            </ResponsiveContainer>
          </div>
        </Card>
        <div className="space-y-6">
          <CountCard title="Industry" items={data.by_industry} />
          <CountCard title="City" items={data.by_city} />
        </div>
      </div>
    </div>
  );
}

function CountCard({ title, items }: { title: string; items: LabelCount[] }) {
  return (
    <Card>
      <h2 className="text-h4 font-semibold text-ink">{title}</h2>
      {items.length === 0 ? <p className="mt-4 text-body text-gray-600">No data yet.</p> : null}
      {items.length > 0 ? (
        <ul className="mt-4 space-y-2">
          {items.map((item) => (
            <li key={item.label} className="flex items-center justify-between text-body text-ink">
              <span>{item.label}</span>
              <span className="font-medium">{item.count}</span>
            </li>
          ))}
        </ul>
      ) : null}
    </Card>
  );
}

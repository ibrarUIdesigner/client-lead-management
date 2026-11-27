import { useState } from "react";
import { Link } from "react-router-dom";
import {
  CartesianGrid,
  Legend,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";

import { QueryGate } from "../components/feedback/QueryGate";
import { PageHeader } from "../components/layout/PageHeader";
import { Badge } from "../components/ui/Badge";
import { Card } from "../components/ui/Card";
import { LearningCard } from "../features/automation/AutomationSettingsCard";
import { useInsights } from "../hooks/useInsights";
import type { Activity, AngleRow, Insights, MarketRow, SeriesPoint } from "../services/insights";

const angleLabels: Record<string, string> = {
  no_website: "No website",
  outdated: "Outdated design",
  slow: "Slow or poor mobile",
  ux: "Usability problems",
  other: "General improvement",
};

const money = new Intl.NumberFormat(undefined, { style: "currency", currency: "USD", maximumFractionDigits: 0 });

export function InsightsPage() {
  const query = useInsights(90);
  return (
    <>
      <PageHeader
        title="Performance & Insights"
        description="What the automation did, what is working, and where to look next. Ranked by replies and clients, not by volume."
      />
      <QueryGate
        pending={query.isPending}
        error={query.error}
        onRetry={() => void query.refetch()}
        fallback="The insights could not be loaded."
        loadingLabel="Loading insights"
      >
        {query.data ? <Dashboard data={query.data} /> : null}
      </QueryGate>
    </>
  );
}

function Dashboard({ data }: { data: Insights }) {
  return (
    <div className="space-y-6">
      <Today activity={data.today} />
      <Attention data={data} />
      <Trends data={data} />
      <Rates data={data} />
      <div className="grid gap-6 xl:grid-cols-2">
        <MarketTable title="Best categories" rows={data.categories} />
        <MarketTable title="Best countries" rows={data.countries} />
      </div>
      <div className="grid gap-6 xl:grid-cols-2">
        <Angles data={data} />
        <MockupCard data={data} />
      </div>
      <OfferTypes data={data} />
      <Explore data={data} />
      <LearningCard learning={data.learning} />
      <Card>
        <h2 className="text-h3 font-semibold text-ink">For tomorrow</h2>
        {data.recommendations.length ? (
          <ul className="mt-3 list-disc space-y-2 pl-5 text-body text-ink">
            {data.recommendations.map((tip) => (
              <li key={tip}>{tip}</li>
            ))}
          </ul>
        ) : (
          <p className="mt-2 text-body text-gray-600">Nothing to change right now.</p>
        )}
      </Card>
    </div>
  );
}

function Stat({ label, value, hint }: { label: string; value: string | number; hint?: string }) {
  return (
    <div className="rounded-card border border-gray-200 px-4 py-3">
      <p className="text-h3 font-semibold text-ink">{value}</p>
      <p className="text-small text-gray-600">{label}</p>
      {hint ? <p className="text-caption text-gray-500">{hint}</p> : null}
    </div>
  );
}

function Today({ activity }: { activity: Activity }) {
  return (
    <Card>
      <h2 className="text-h3 font-semibold text-ink">Today</h2>
      <div className="mt-4 grid grid-cols-2 gap-3 sm:grid-cols-5">
        <Stat label="Leads found" value={activity.leads_discovered} hint={`${activity.leads_rejected} left out`} />
        <Stat label="Leads qualified" value={activity.leads_qualified} />
        <Stat label="Audits done" value={activity.audits_completed} />
        <Stat label="Mockups made" value={activity.mockups_generated} />
        <Stat
          label="Emails sent"
          value={activity.emails_sent}
          hint={`${activity.first_emails} first, ${activity.followups_sent} follow-up`}
        />
        <Stat label="Replies" value={activity.replies} />
        <Stat label="Positive replies" value={activity.positive_replies} />
        <Stat label="Interested" value={activity.interested} />
        <Stat label="Meetings" value={activity.meetings} />
        <Stat label="New clients" value={activity.clients_won} />
      </div>
      <p className="mt-3 text-small text-gray-600">
        {activity.bounces} bounced, {activity.unsubscribes} unsubscribed. Delivered is an estimate
        (sent minus bounces) because Gmail gives no delivery receipts.
      </p>
    </Card>
  );
}

function Attention({ data }: { data: Insights }) {
  const { promising, waiting } = data;
  if (!promising.length && !waiting.drafts && !waiting.followups_due) return null;
  return (
    <Card>
      <h2 className="text-h3 font-semibold text-ink">Needs you</h2>
      <div className="mt-3 flex flex-wrap gap-2">
        {waiting.drafts ? (
          <Link to="/approvals">
            <Badge tone="orange">{waiting.drafts} drafts to approve</Badge>
          </Link>
        ) : null}
        {waiting.followups_due ? (
          <Link to="/follow-ups">
            <Badge tone="blue">{waiting.followups_due} follow-ups due</Badge>
          </Link>
        ) : null}
      </div>
      {promising.length ? (
        <ul className="mt-3 divide-y divide-gray-100">
          {promising.map((lead) => (
            <li key={lead.lead_id} className="flex flex-wrap items-center justify-between gap-2 py-2">
              <Link to={`/leads/${lead.lead_id}`} className="font-medium text-primary hover:underline">
                {lead.business_name}
              </Link>
              <span className="flex items-center gap-2 text-small text-gray-600">
                {[lead.category, lead.country].filter(Boolean).join(" · ")}
                {lead.unread ? <Badge tone="red">Unread reply</Badge> : null}
                <Badge tone={lead.outcome === "meeting" ? "green" : "indigo"}>{lead.outcome}</Badge>
              </span>
            </li>
          ))}
        </ul>
      ) : null}
    </Card>
  );
}

function Trends({ data }: { data: Insights }) {
  const [period, setPeriod] = useState<"daily" | "weekly" | "monthly">("daily");
  const series: SeriesPoint[] =
    period === "daily" ? data.daily.slice(-30) : period === "weekly" ? data.weekly : data.monthly;
  return (
    <Card>
      <div className="flex flex-wrap items-center justify-between gap-3">
        <h2 className="text-h3 font-semibold text-ink">Trends</h2>
        <div className="flex gap-1" role="group" aria-label="Trend period">
          {(["daily", "weekly", "monthly"] as const).map((item) => (
            <button
              key={item}
              type="button"
              aria-pressed={period === item}
              onClick={() => setPeriod(item)}
              className={`rounded-md px-3 py-1.5 text-small font-medium capitalize ${
                period === item ? "bg-primary text-white" : "text-gray-600 hover:bg-gray-100"
              }`}
            >
              {item}
            </button>
          ))}
        </div>
      </div>
      <div className="mt-4 h-72 w-full">
        <ResponsiveContainer width="100%" height="100%">
          <LineChart data={series} margin={{ top: 8, right: 12, bottom: 0, left: -12 }}>
            <CartesianGrid strokeDasharray="3 3" stroke="#e5e7eb" />
            <XAxis dataKey="date" tick={{ fontSize: 11 }} tickFormatter={(v: string) => v.slice(5)} />
            <YAxis allowDecimals={false} tick={{ fontSize: 11 }} />
            <Tooltip />
            <Legend />
            <Line type="monotone" dataKey="discovered" name="Leads found" stroke="#4f46e5" dot={false} strokeWidth={2} />
            <Line type="monotone" dataKey="sent" name="First emails" stroke="#0f766e" dot={false} strokeWidth={2} />
            <Line type="monotone" dataKey="replies" name="Replies" stroke="#b45309" dot={false} strokeWidth={2} />
            <Line type="monotone" dataKey="positive" name="Positive" stroke="#1d4ed8" dot={false} strokeWidth={2} />
          </LineChart>
        </ResponsiveContainer>
      </div>
    </Card>
  );
}

function Rates({ data }: { data: Insights }) {
  const { funnel, rates } = data;
  return (
    <Card>
      <h2 className="text-h3 font-semibold text-ink">Outreach results, all time</h2>
      <div className="mt-4 grid grid-cols-2 gap-3 sm:grid-cols-5">
        <Stat label="Leads" value={funnel.leads} />
        <Stat label="Emailed" value={funnel.emailed} />
        <Stat label="Replied" value={funnel.replied} hint={`${rates.reply_rate}% reply rate`} />
        <Stat label="Positive" value={funnel.positive} hint={`${rates.positive_rate}% positive rate`} />
        <Stat label="Clients" value={funnel.clients} hint={`${rates.conversion_rate}% of emails`} />
      </div>
      <p className="mt-3 text-small text-gray-600">
        Rates are per first email sent. Opens and clicks are not tracked on purpose, because they
        do not predict clients.
      </p>
    </Card>
  );
}

function MarketTable({ title, rows }: { title: string; rows: MarketRow[] }) {
  const shown = rows.slice(0, 10);
  return (
    <Card>
      <h2 className="text-h3 font-semibold text-ink">{title}</h2>
      {shown.length === 0 ? (
        <p className="mt-2 text-body text-gray-600">Nothing yet.</p>
      ) : (
        <div className="mt-3 overflow-x-auto">
          <table className="w-full text-left text-small">
            <thead className="text-gray-600">
              <tr>
                <th className="py-2 pr-3 font-medium">Name</th>
                <th className="py-2 pr-3 font-medium">Leads</th>
                <th className="py-2 pr-3 font-medium">Sent</th>
                <th className="py-2 pr-3 font-medium">Reply</th>
                <th className="py-2 pr-3 font-medium">Positive</th>
                <th className="py-2 pr-3 font-medium">Clients</th>
                <th className="py-2 font-medium">Revenue</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-100">
              {shown.map((row) => (
                <tr key={row.label}>
                  <td className="py-2 pr-3 font-medium text-ink">
                    {row.label}
                    {!row.enough_data && row.sent > 0 ? (
                      <span className="ml-2 text-caption font-normal text-gray-500">early</span>
                    ) : null}
                  </td>
                  <td className="py-2 pr-3">{row.qualified_leads}</td>
                  <td className="py-2 pr-3">{row.sent}</td>
                  <td className="py-2 pr-3">{row.sent ? `${row.reply_rate}%` : "-"}</td>
                  <td className="py-2 pr-3">{row.sent ? `${row.positive_rate}%` : "-"}</td>
                  <td className="py-2 pr-3">{row.clients}</td>
                  <td className="py-2">{row.revenue ? money.format(row.revenue) : "-"}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
      <p className="mt-3 text-caption text-gray-500">
        Ranked by quality, not volume. Rows marked early have fewer than 15 emails, so their
        rates may change a lot.
      </p>
    </Card>
  );
}

function AngleList({ rows }: { rows: AngleRow[] }) {
  return (
    <ul className="mt-3 divide-y divide-gray-100">
      {rows.map((row) => (
        <li key={row.label} className="flex flex-wrap items-center justify-between gap-2 py-2 text-small">
          <span className="font-medium text-ink">{angleLabels[row.label] ?? row.label}</span>
          <span className="text-gray-600">
            {row.sent} sent, {row.sent ? `${row.reply_rate}% reply, ${row.positive_rate}% positive` : "no data"}
            {!row.enough_data && row.sent > 0 ? " (early)" : ""}
          </span>
        </li>
      ))}
    </ul>
  );
}

function Angles({ data }: { data: Insights }) {
  return (
    <Card>
      <h2 className="text-h3 font-semibold text-ink">Which angle works</h2>
      {data.strategies.length === 0 ? (
        <p className="mt-2 text-body text-gray-600">Shown after the first emails are sent.</p>
      ) : (
        <AngleList rows={data.strategies} />
      )}
      {data.variants.length > 0 ? (
        <>
          <h3 className="mt-4 text-body font-semibold text-ink">Writing styles</h3>
          <AngleList rows={data.variants} />
        </>
      ) : null}
    </Card>
  );
}

function MockupCard({ data }: { data: Insights }) {
  const { with_mockup: withMockup, without_mockup: withoutMockup } = data.mockup_effect;
  return (
    <Card>
      <h2 className="text-h3 font-semibold text-ink">Mockup link or not</h2>
      <div className="mt-3 grid grid-cols-2 gap-3">
        <Stat
          label="With a mockup link"
          value={withMockup.sent ? `${withMockup.positive_rate}%` : "-"}
          hint={`${withMockup.sent} sent, ${withMockup.reply_rate}% reply`}
        />
        <Stat
          label="Without"
          value={withoutMockup.sent ? `${withoutMockup.positive_rate}%` : "-"}
          hint={`${withoutMockup.sent} sent, ${withoutMockup.reply_rate}% reply`}
        />
      </div>
      <p className="mt-3 text-small text-gray-600">
        Positive reply rate. A fair comparison needs about 15 emails in each group.
      </p>
    </Card>
  );
}


function OfferTypes({ data }: { data: Insights }) {
  if (data.offer_types.length === 0) return null;
  const cell = (group: { sent: number; positive_rate: number; enough_data: boolean }) =>
    group.sent ? `${group.positive_rate}% of ${group.sent}${group.enough_data ? "" : " (early)"}` : "-";
  return (
    <Card>
      <h2 className="text-h3 font-semibold text-ink">New website or redesign?</h2>
      <p className="mt-1 text-small text-gray-600">
        Positive reply rate by category, for businesses with no website against businesses with
        one that could be better.
      </p>
      <div className="mt-3 overflow-x-auto">
        <table className="w-full text-left text-small">
          <thead className="text-gray-600">
            <tr>
              <th className="py-2 pr-3 font-medium">Category</th>
              <th className="py-2 pr-3 font-medium">New website offer</th>
              <th className="py-2 font-medium">Redesign offer</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-gray-100">
            {data.offer_types.map((row) => (
              <tr key={row.label}>
                <td className="py-2 pr-3 font-medium text-ink">{row.label}</td>
                <td className="py-2 pr-3">{cell(row.new_site)}</td>
                <td className="py-2">{cell(row.redesign)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </Card>
  );
}

function Explore({ data }: { data: Insights }) {
  if (data.explore.length === 0) return null;
  return (
    <Card>
      <h2 className="text-h3 font-semibold text-ink">Worth exploring</h2>
      <ul className="mt-3 divide-y divide-gray-100">
        {data.explore.map((idea) => (
          <li key={`${idea.kind}-${idea.name}`} className="py-2 text-body text-ink">
            <span className="font-medium">{idea.name}</span> <Badge tone="gray">{idea.kind}</Badge>
            <p className="text-small text-gray-600">{idea.reason}</p>
          </li>
        ))}
      </ul>
      <p className="mt-2 text-caption text-gray-500">
        Add these under Targets on the Automation page to include them in the daily search.
      </p>
    </Card>
  );
}

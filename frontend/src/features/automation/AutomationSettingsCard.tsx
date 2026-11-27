import { CheckCircle2, CircleAlert } from "lucide-react";

import { LoadingState } from "../../components/feedback/LoadingState";
import { useToast } from "../../components/feedback/useToast";
import { Badge } from "../../components/ui/Badge";
import { Card } from "../../components/ui/Card";
import { Switch } from "../../components/ui/Switch";
import { useAutomation, useUpdateAutomationFlags } from "../../hooks/usePipeline";
import type {
  AutomationFlags,
  DiscoveryOverview,
  LearningOverview,
  OutreachOverview,
} from "../../services/pipeline";

const switches: { key: keyof AutomationFlags; label: string; help: string }[] = [
  {
    key: "followups_auto_send",
    label: "Send Day 4 and Day 10 follow-ups automatically",
    help: "Sent in the same email thread. A reply, bounce or opt-out cancels the rest.",
  },
  {
    key: "breakup_auto_send",
    label: "Send the Day 20 closing note automatically",
    help: "Off by default. When off, the closing note waits for you.",
  },
];

const rejectionLabels: Record<string, string> = {
  excluded: "on your do-not-contact list",
  chain: "national chains",
  no_contact: "no way to contact",
  not_preferred: "not a preferred opportunity",
  low_score: "below the score threshold",
};

function topList(values: Record<string, number>): string {
  const entries = Object.entries(values).filter(([key]) => key);
  return entries.length ? entries.map(([key, count]) => `${key} ${count}`).join(", ") : "none yet";
}

function DiscoveryCard({ discovery }: { discovery: DiscoveryOverview }) {
  const rejected = Object.entries(discovery.rejected_today);
  return (
    <Card>
      <div className="flex flex-wrap items-center justify-between gap-3">
        <h3 className="text-h4 font-semibold text-ink">Finding leads today</h3>
        <Badge tone={discovery.enabled ? "green" : "gray"}>
          {discovery.enabled ? "On" : "Off"}
        </Badge>
      </div>
      <p className="mt-3 text-h3 font-semibold text-ink">
        {discovery.created_today}
        <span className="text-body font-normal text-gray-600"> of {discovery.limit} leads found</span>
      </p>
      <dl className="mt-3 grid gap-3 sm:grid-cols-2">
        <div>
          <dt className="text-small text-gray-600">By country</dt>
          <dd className="text-body text-ink">{topList(discovery.by_country)}</dd>
        </div>
        <div>
          <dt className="text-small text-gray-600">By category</dt>
          <dd className="text-body text-ink">{topList(discovery.by_category)}</dd>
        </div>
        <div>
          <dt className="text-small text-gray-600">Left out today</dt>
          <dd className="text-body text-ink">
            {rejected.length
              ? rejected
                  .map(([reason, count]) => `${count} ${rejectionLabels[reason] ?? reason}`)
                  .join(", ")
              : "nothing"}
          </dd>
        </div>
        <div>
          <dt className="text-small text-gray-600">Markets</dt>
          <dd className="text-body text-ink">
            {discovery.markets_searched} of {discovery.markets_total} searched,{" "}
            {discovery.markets_resting} resting
          </dd>
        </div>
      </dl>
    </Card>
  );
}

function OutreachCard({ outreach }: { outreach: OutreachOverview }) {
  return (
    <Card>
      <h3 className="text-h4 font-semibold text-ink">Today's outreach</h3>
      <p className="mt-3 text-h3 font-semibold text-ink">
        {outreach.drafted_today}
        <span className="text-body font-normal text-gray-600">
          {" "}
          of {outreach.daily_limit} emails written, {outreach.sent_today} sent
        </span>
      </p>
      <p className="mt-1 text-small text-gray-600">
        {outreach.waiting} {outreach.waiting === 1 ? "lead is" : "leads are"} waiting for a free
        slot. The strongest leads are written first, and a better lead found later can take the
        next slot.
      </p>
      {outreach.next_up.length > 0 ? (
        <ol className="mt-3 divide-y divide-gray-100">
          {outreach.next_up.map((item) => (
            <li key={item.lead_id} className="flex flex-wrap items-baseline justify-between gap-2 py-2">
              <div className="min-w-0">
                <p className="text-body font-medium text-ink">
                  {item.business_name}
                  {item.country ? <span className="text-gray-600"> · {item.country}</span> : null}
                </p>
                <p className="text-small text-gray-600">{item.reasons.join(", ")}</p>
              </div>
              <Badge tone="indigo">Priority {item.priority}</Badge>
            </li>
          ))}
        </ol>
      ) : null}
    </Card>
  );
}

export function LearningCard({ learning }: { learning: LearningOverview }) {
  const empty = learning.boosted.length === 0 && learning.reduced.length === 0;
  const name = (item: { kind: string; name: string; factor: number }) =>
    `${item.name} (${item.kind}) x${item.factor.toFixed(2)}`;
  const latest = learning.recent_moves[0];
  return (
    <Card>
      <div className="flex flex-wrap items-center justify-between gap-3">
        <h3 className="text-h4 font-semibold text-ink">What it has learned</h3>
        <Badge tone={learning.enabled ? "green" : "gray"}>{learning.enabled ? "On" : "Off"}</Badge>
      </div>
      {empty ? (
        <p className="mt-3 text-small text-gray-600">
          Nothing yet. Learning starts after {learning.min_total_sends} emails in total, and judges
          a category, country or style after {learning.min_key_sends} emails of its own.
        </p>
      ) : (
        <dl className="mt-3 grid gap-3 sm:grid-cols-2">
          <div>
            <dt className="text-small text-gray-600">Getting more effort</dt>
            <dd className="text-body text-ink">
              {learning.boosted.length ? learning.boosted.map(name).join(", ") : "none"}
            </dd>
          </div>
          <div>
            <dt className="text-small text-gray-600">Getting less</dt>
            <dd className="text-body text-ink">
              {learning.reduced.length ? learning.reduced.map(name).join(", ") : "none"}
            </dd>
          </div>
        </dl>
      )}
      {latest ? (
        <p className="mt-3 text-caption text-gray-500">
          Latest change: {latest.name} ({latest.kind}) {latest.from.toFixed(2)} to{" "}
          {latest.to.toFixed(2)} after {latest.sent} emails.
        </p>
      ) : null}
    </Card>
  );
}

function formatTick(at: string, now: number): string {
  const minutes = Math.round((now - new Date(at).getTime()) / 60_000);
  if (minutes < 1) return "just now";
  if (minutes < 60) return `${minutes} min ago`;
  return `${Math.round(minutes / 60)} h ago`;
}

export function AutomationSettingsCard() {
  const { notify } = useToast();
  const query = useAutomation();
  const update = useUpdateAutomationFlags();

  if (query.isPending) return <LoadingState label="Loading automation" />;
  if (query.isError || !query.data) {
    return (
      <Card>
        <p className="text-body text-red-800" role="alert">
          Automation status is unavailable. Check that the API is running.
        </p>
      </Card>
    );
  }

  const data = query.data;
  // The time of the last fetch is used as "now" so rendering stays pure.
  const now = query.dataUpdatedAt;
  const tickAge = data.last_tick ? now - new Date(data.last_tick.at).getTime() : null;
  const tickStale = tickAge === null || tickAge > 45 * 60_000;
  const missing = data.readiness.filter((item) => !item.ok);

  function toggle(key: keyof AutomationFlags, value: boolean) {
    update.mutate(
      { [key]: value },
      {
        onSuccess: () => notify(value ? "Switched on." : "Switched off.", "success"),
        onError: () => notify("Could not save that change.", "danger"),
      },
    );
  }

  return (
    <div className="space-y-6">
      <Card>
        <div className="flex flex-wrap items-center justify-between gap-3">
          <h2 className="text-h3 font-semibold text-ink">Automation</h2>
          <Badge tone={tickStale ? "orange" : "green"}>
            {data.last_tick ? `Last run ${formatTick(data.last_tick.at, now)}` : "Has not run yet"}
          </Badge>
        </div>
        <p className="mt-2 max-w-2xl text-body leading-relaxed text-gray-600">
          Leads are found, scored, audited, researched and given a mockup and a draft on their own.
          Whether first emails go out on their own is set under Settings, in Outreach mode. The
          switches below cover follow-ups. Everything is off until you turn it on.
        </p>
        {tickStale ? (
          <p className="mt-3 text-small text-amber-800" role="status">
            The scheduler has not run in the last 45 minutes. Check the GitHub Actions workflow
            and its APP_URL and CRON_SECRET secrets.
          </p>
        ) : null}
        <div className="mt-4 divide-y divide-gray-100">
          {switches.map((item) => (
            <div key={item.key} className="py-2">
              <Switch
                label={item.label}
                checked={data.flags[item.key]}
                disabled={update.isPending}
                onCheckedChange={(value) => toggle(item.key, value)}
              />
              <p className="max-w-2xl pb-2 text-small leading-relaxed text-gray-600">{item.help}</p>
            </div>
          ))}
        </div>
      </Card>

      <DiscoveryCard discovery={data.discovery} />
      <OutreachCard outreach={data.outreach} />
      <LearningCard learning={data.learning} />

      <Card>
        <h3 className="text-h4 font-semibold text-ink">Before it can run on its own</h3>
        <ul className="mt-3 space-y-2">
          {data.readiness.map((item) => (
            <li key={item.key} className="flex items-start gap-2 text-body">
              {item.ok ? (
                <CheckCircle2 className="mt-0.5 size-4 shrink-0 text-emerald-600" aria-hidden />
              ) : (
                <CircleAlert className="mt-0.5 size-4 shrink-0 text-amber-600" aria-hidden />
              )}
              <span className="text-ink">
                {item.label}
                {item.ok ? null : (
                  <span className="block text-small text-gray-600">{item.hint}</span>
                )}
              </span>
            </li>
          ))}
        </ul>
        {missing.length === 0 ? (
          <p className="mt-3 text-small text-emerald-800">Everything needed is set up.</p>
        ) : null}
      </Card>

      <Card>
        <h3 className="text-h4 font-semibold text-ink">Today</h3>
        <dl className="mt-3 grid gap-4 sm:grid-cols-3">
          <div>
            <dt className="text-small text-gray-600">Emails sent</dt>
            <dd className="text-h4 font-semibold text-ink">
              {data.sent_today}
              {data.daily_cap ? ` of ${data.daily_cap}` : ""}
            </dd>
          </div>
          <div>
            <dt className="text-small text-gray-600">Send window</dt>
            <dd className="text-body text-ink">
              {data.send_window.start_hour}:00 to {data.send_window.end_hour}:00,{" "}
              {data.send_window.timezone}, weekdays
              <span className="ml-2">
                <Badge tone={data.send_window.open_now ? "green" : "gray"}>
                  {data.send_window.open_now ? "Open" : "Closed"}
                </Badge>
              </span>
            </dd>
          </div>
          <div>
            <dt className="text-small text-gray-600">Minimum lead score</dt>
            <dd className="text-h4 font-semibold text-ink">{data.pipeline.min_score}</dd>
          </div>
        </dl>
        <div className="mt-5 grid gap-2 sm:grid-cols-2">
          {Object.entries(data.pipeline.budgets).map(([step, budget]) => (
            <p key={step} className="text-small text-gray-600">
              <span className="capitalize text-ink">{step}</span>: {budget.used} of {budget.limit}{" "}
              used today
            </p>
          ))}
        </div>
        <p className="mt-4 text-small text-gray-600">
          Queue: {data.pipeline.jobs.QUEUED ?? 0} waiting, {data.pipeline.jobs.RUNNING ?? 0}{" "}
          running, {data.pipeline.jobs.FAILED ?? 0} failed.
        </p>
      </Card>
    </div>
  );
}

import { useState, type FormEvent } from "react";
import { Link } from "react-router-dom";
import { Pause, Play, Trash2 } from "lucide-react";

import { QueryGate } from "../components/feedback/QueryGate";
import { useToast } from "../components/feedback/useToast";
import { PageHeader } from "../components/layout/PageHeader";
import { Badge, type BadgeTone } from "../components/ui/Badge";
import { Button } from "../components/ui/Button";
import { Card } from "../components/ui/Card";
import { Checkbox } from "../components/ui/Checkbox";
import { Input } from "../components/ui/Input";
import { Select } from "../components/ui/Select";
import { Textarea } from "../components/ui/Textarea";
import { AutomationSettingsCard } from "../features/automation/AutomationSettingsCard";
import { useReportActions } from "../hooks/useInsights";
import {
  useActivityLog,
  useAutomationConfig,
  useAutomationConfigActions,
  useExclusions,
} from "../hooks/usePipeline";
import { apiErrorMessage } from "../lib/apiError";
import { formatWhen } from "../lib/format";
import type { AutomationConfig, AutomationRun, Exclusion } from "../services/pipeline";

const businessTypes: { value: string; label: string }[] = [
  { value: "no_website", label: "No website" },
  { value: "outdated", label: "Outdated design" },
  { value: "slow", label: "Slow or poor mobile" },
  { value: "ux", label: "Usability problems" },
];

const runTone: Record<AutomationRun["status"], BadgeTone> = {
  RUNNING: "blue",
  OK: "green",
  SKIPPED: "gray",
  FAILED: "red",
};

function lines(value: string): string[] {
  return value
    .split(/[\n,]/)
    .map((item) => item.trim())
    .filter(Boolean);
}

export function AutomationPage() {
  const query = useAutomationConfig();
  const actions = useAutomationConfigActions();
  const { notify } = useToast();

  function toggleRunning(config: AutomationConfig) {
    const action = config.paused ? actions.resume : actions.pause;
    action.mutate(undefined, {
      onSuccess: () => notify(config.paused ? "Automation resumed." : "Automation paused.", "success"),
      onError: (error) => notify(apiErrorMessage(error, "Could not change that."), "danger"),
    });
  }

  return (
    <>
      <PageHeader
        title="Automation"
        description="Choose what runs on its own, how much, and where. Changes apply on the next cycle."
        actions={
          query.data ? (
            <Button
              variant={query.data.paused ? "primary" : "secondary"}
              onClick={() => toggleRunning(query.data)}
              isLoading={actions.pause.isPending || actions.resume.isPending}
            >
              {query.data.paused ? <Play className="size-4" aria-hidden /> : <Pause className="size-4" aria-hidden />}
              {query.data.paused ? "Resume automation" : "Pause automation"}
            </Button>
          ) : null
        }
      />
      <div className="space-y-6">
        {query.data?.paused ? (
          <p
            className="rounded-card border border-amber-200 bg-amber-50 px-4 py-3 text-body text-amber-900"
            role="status"
          >
            Automation is paused. Nothing is discovered, drafted or sent until you resume. Replies
            are still tracked.
          </p>
        ) : null}
        <QueryGate
          pending={query.isPending}
          error={query.error}
          onRetry={() => void query.refetch()}
          fallback="Automation settings could not be loaded."
          loadingLabel="Loading automation settings"
        >
          {query.data ? <ConfigForm key={query.dataUpdatedAt} initial={query.data} /> : null}
        </QueryGate>
        <ExclusionsCard />
        <AutomationSettingsCard />
        <LogCard />
      </div>
    </>
  );
}

function ConfigForm({ initial }: { initial: AutomationConfig }) {
  const { notify } = useToast();
  const { save } = useAutomationConfigActions();
  const [form, setForm] = useState({
    discovery: String(initial.discovery_daily_limit),
    outreach: String(initial.outreach_daily_limit),
    countries: initial.target_countries.join("\n"),
    categories: initial.target_categories.join("\n"),
    types: initial.business_types,
    minScore: String(initial.min_score),
    intervals: initial.followup_intervals.join(", "),
    attempts: String(initial.followup_max_attempts),
    reportTime: initial.report_time,
    reportTimezone: initial.report_timezone,
    reportEmail: initial.report_email,
    mode: initial.outreach_mode,
    learning: initial.learning_enabled,
    pinnedCategories: initial.pinned_categories.join("\n"),
    pinnedCountries: initial.pinned_countries.join("\n"),
    excludedCountries: initial.excluded_countries.join("\n"),
  });
  const set = <K extends keyof typeof form>(key: K, value: (typeof form)[K]) =>
    setForm((current) => ({ ...current, [key]: value }));

  function submit(event: FormEvent) {
    event.preventDefault();
    const config: AutomationConfig = {
      paused: initial.paused,
      discovery_daily_limit: Number(form.discovery) || 0,
      outreach_daily_limit: Number(form.outreach) || 0,
      target_countries: lines(form.countries),
      target_categories: lines(form.categories),
      business_types: form.types,
      min_score: Number(form.minScore) || 0,
      followup_intervals: lines(form.intervals).map(Number).filter((n) => Number.isFinite(n)),
      followup_max_attempts: Number(form.attempts) || 0,
      report_time: form.reportTime,
      report_timezone: form.reportTimezone.trim() || "UTC",
      report_email: form.reportEmail.trim(),
      outreach_mode: form.mode,
      learning_enabled: form.learning,
      pinned_categories: lines(form.pinnedCategories),
      pinned_countries: lines(form.pinnedCountries),
      excluded_countries: lines(form.excludedCountries),
    };
    save.mutate(config, {
      onSuccess: () => notify("Automation settings saved.", "success"),
      onError: (error) => notify(apiErrorMessage(error, "Could not save the settings."), "danger"),
    });
  }

  return (
    <form onSubmit={submit} className="space-y-6">
      <Card>
        <h2 className="text-h3 font-semibold text-ink">Outreach mode</h2>
        <div className="mt-4 max-w-md">
          <Select
            label="How first emails are sent"
            value={form.mode}
            onChange={(event) => set("mode", event.target.value as "approval" | "automatic")}
            options={[
              { value: "approval", label: "Approval: I review every email (recommended)" },
              { value: "automatic", label: "Automatic: send within limits and safety rules" },
            ]}
            hint="Automatic mode still holds anything that fails the quality check. Follow-up switches are below."
          />
        </div>
        <p className="mt-3 text-small text-gray-600">
          In approval mode, drafts wait on the{" "}
          <Link to="/approvals" className="font-medium text-primary hover:underline">
            Approvals
          </Link>{" "}
          page.
        </p>
      </Card>

      <Card>
        <h2 className="text-h3 font-semibold text-ink">Daily limits and quality</h2>
        <div className="mt-4 grid gap-4 sm:grid-cols-3">
          <Input
            label="Leads to find per day"
            type="number"
            min={0}
            max={500}
            value={form.discovery}
            onChange={(event) => set("discovery", event.target.value)}
          />
          <Input
            label="Emails to send per day"
            type="number"
            min={0}
            max={200}
            value={form.outreach}
            onChange={(event) => set("outreach", event.target.value)}
          />
          <Input
            label="Minimum lead score"
            type="number"
            min={0}
            max={100}
            value={form.minScore}
            onChange={(event) => set("minScore", event.target.value)}
            hint="Leads below this are ignored."
          />
        </div>
      </Card>

      <Card>
        <h2 className="text-h3 font-semibold text-ink">Targets</h2>
        <div className="mt-4 grid gap-4 md:grid-cols-2">
          <Textarea
            label="Countries"
            rows={5}
            value={form.countries}
            onChange={(event) => set("countries", event.target.value)}
            hint="One per line. Leave empty to search everywhere."
          />
          <Textarea
            label="Business categories"
            rows={5}
            value={form.categories}
            onChange={(event) => set("categories", event.target.value)}
            hint="One per line, for example dentist or plumber. Leave empty for all."
          />
        </div>
        <fieldset className="mt-4">
          <legend className="text-small font-medium text-gray-700">Preferred opportunities</legend>
          <div className="mt-1 flex flex-wrap gap-x-6">
            {businessTypes.map((type) => (
              <Checkbox
                key={type.value}
                label={type.label}
                checked={form.types.includes(type.value)}
                onChange={(event) =>
                  set(
                    "types",
                    event.target.checked
                      ? [...form.types, type.value]
                      : form.types.filter((item) => item !== type.value),
                  )
                }
              />
            ))}
          </div>
        </fieldset>
      </Card>

      <Card>
        <h2 className="text-h3 font-semibold text-ink">Learning from results</h2>
        <p className="mt-1 max-w-2xl text-small text-gray-600">
          Effort shifts slowly toward the categories, countries, angles and writing styles that
          earn positive replies, interested prospects, meetings and clients. Nothing moves until
          there are enough emails, and nothing changes by more than 10% a day.
        </p>
        <div className="mt-3 max-w-md">
          <Checkbox
            label="Learn from results"
            checked={form.learning}
            onChange={(event) => set("learning", event.target.checked)}
          />
        </div>
        <div className="mt-3 grid gap-4 md:grid-cols-3">
          <Textarea
            label="Always favour these categories"
            rows={4}
            value={form.pinnedCategories}
            onChange={(event) => set("pinnedCategories", event.target.value)}
            hint="One per line. Gets a fixed boost whatever the results say."
          />
          <Textarea
            label="Always favour these countries"
            rows={4}
            value={form.pinnedCountries}
            onChange={(event) => set("pinnedCountries", event.target.value)}
            hint="One per line."
          />
          <Textarea
            label="Never search or email these countries"
            rows={4}
            value={form.excludedCountries}
            onChange={(event) => set("excludedCountries", event.target.value)}
            hint="One per line."
          />
        </div>
      </Card>

      <Card>
        <h2 className="text-h3 font-semibold text-ink">Follow-ups</h2>
        <div className="mt-4 grid gap-4 sm:grid-cols-2">
          <Input
            label="Days after the first email"
            value={form.intervals}
            onChange={(event) => set("intervals", event.target.value)}
            hint="Comma separated, for example 4, 10, 20."
          />
          <Input
            label="Maximum follow-ups"
            type="number"
            min={0}
            max={6}
            value={form.attempts}
            onChange={(event) => set("attempts", event.target.value)}
            hint="0 turns follow-ups off."
          />
        </div>
      </Card>

      <Card>
        <h2 className="text-h3 font-semibold text-ink">Daily report</h2>
        <div className="mt-4 grid gap-4 sm:grid-cols-3">
          <Input
            label="Report time"
            type="time"
            value={form.reportTime}
            onChange={(event) => set("reportTime", event.target.value)}
          />
          <Input
            label="Time zone"
            value={form.reportTimezone}
            onChange={(event) => set("reportTimezone", event.target.value)}
            hint="For example Asia/Karachi."
          />
          <Input
            label="Send the report to"
            type="email"
            value={form.reportEmail}
            onChange={(event) => set("reportEmail", event.target.value)}
          />
        </div>
        <ReportActions />
      </Card>

      <div className="flex justify-end">
        <Button type="submit" isLoading={save.isPending}>
          Save settings
        </Button>
      </div>
    </form>
  );
}

const exclusionKinds = [
  { value: "domain", label: "Website domain" },
  { value: "email", label: "Email address" },
  { value: "name", label: "Business name contains" },
  { value: "category", label: "Category" },
];

function ExclusionsCard() {
  const { notify } = useToast();
  const { query, add, remove } = useExclusions();
  const [kind, setKind] = useState<Exclusion["kind"]>("domain");
  const [value, setValue] = useState("");

  function submit(event: FormEvent) {
    event.preventDefault();
    if (!value.trim()) return;
    add.mutate(
      { kind, value },
      {
        onSuccess: () => {
          setValue("");
          notify("Added to the do-not-contact list.", "success");
        },
        onError: (error) => notify(apiErrorMessage(error, "Could not add that."), "danger"),
      },
    );
  }

  return (
    <Card>
      <h2 className="text-h3 font-semibold text-ink">Do-not-contact list</h2>
      <p className="mt-1 max-w-2xl text-small text-gray-600">
        Matching businesses are never discovered, drafted for, or emailed, including by hand.
      </p>
      <form onSubmit={submit} className="mt-4 flex flex-col gap-3 sm:flex-row sm:items-end">
        <div className="sm:w-56">
          <Select
            label="Type"
            value={kind}
            onChange={(event) => setKind(event.target.value as Exclusion["kind"])}
            options={exclusionKinds}
          />
        </div>
        <div className="sm:flex-1">
          <Input label="Value" value={value} onChange={(event) => setValue(event.target.value)} />
        </div>
        <Button type="submit" variant="secondary" isLoading={add.isPending}>
          Add
        </Button>
      </form>
      {query.data && query.data.length > 0 ? (
        <ul className="mt-4 divide-y divide-gray-100">
          {query.data.map((item) => (
            <li key={item.id} className="flex items-center justify-between gap-3 py-2">
              <span className="min-w-0 text-body text-ink">
                <Badge tone="gray">{item.kind}</Badge>{" "}
                <span className="break-all">{item.value}</span>
              </span>
              <Button
                variant="ghost"
                size="icon-sm"
                aria-label={`Remove ${item.value}`}
                onClick={() =>
                  remove.mutate(item.id, {
                    onError: (error) => notify(apiErrorMessage(error, "Could not remove that."), "danger"),
                  })
                }
              >
                <Trash2 className="size-4" aria-hidden />
              </Button>
            </li>
          ))}
        </ul>
      ) : (
        <p className="mt-4 text-small text-gray-600">Nothing is excluded yet.</p>
      )}
    </Card>
  );
}

function LogCard() {
  const query = useActivityLog();
  const data = query.data;
  return (
    <Card>
      <h2 className="text-h3 font-semibold text-ink">Activity and errors</h2>
      {!data ? (
        <p className="mt-3 text-small text-gray-600">
          {query.isError ? "The log could not be loaded." : "Loading the log."}
        </p>
      ) : (
        <>
          {data.failed_jobs.length > 0 ? (
            <div className="mt-3">
              <h3 className="text-body font-semibold text-ink">Steps that failed</h3>
              <ul className="mt-2 divide-y divide-gray-100">
                {data.failed_jobs.map((job) => (
                  <li key={job.id} className="py-2 text-body">
                    <Link to={`/leads/${job.lead_id}`} className="font-medium text-primary hover:underline">
                      {job.business_name ?? "Lead"}
                    </Link>{" "}
                    <span className="text-gray-600">
                      {job.step} after {job.attempts} tries: {job.last_error ?? "no details"}
                    </span>
                  </li>
                ))}
              </ul>
            </div>
          ) : null}
          <h3 className="mt-4 text-body font-semibold text-ink">Recent runs</h3>
          {data.runs.length === 0 ? (
            <p className="mt-2 text-small text-gray-600">
              Nothing has run yet. The scheduler runs about every 10 minutes once it is set up.
            </p>
          ) : (
            <ul className="mt-2 divide-y divide-gray-100">
              {data.runs.map((run) => (
                <li key={run.id} className="flex flex-wrap items-start justify-between gap-2 py-2">
                  <div className="min-w-0">
                    <p className="text-body text-ink">
                      <span className="capitalize">{run.kind}</span>{" "}
                      <span className="text-gray-600">{formatWhen(run.started_at)}</span>
                    </p>
                    {run.error ? <p className="text-small text-red-700">{run.error}</p> : null}
                    {run.summary ? <p className="text-small text-gray-600">{runSummary(run)}</p> : null}
                  </div>
                  <Badge tone={runTone[run.status]}>{run.status.toLowerCase()}</Badge>
                </li>
              ))}
            </ul>
          )}
        </>
      )}
    </Card>
  );
}

function runSummary(run: AutomationRun): string {
  const s = run.summary ?? {};
  const parts: string[] = [];
  if (typeof s.jobs_run === "number") parts.push(`${s.jobs_run} steps`);
  if (typeof s.jobs_failed === "number" && s.jobs_failed > 0) parts.push(`${s.jobs_failed} failed`);
  if (typeof s.followups_sent === "number" && s.followups_sent > 0) parts.push(`${s.followups_sent} follow-ups sent`);
  if (typeof s.stopped_because === "string" && s.stopped_because !== "queue empty") parts.push(s.stopped_because);
  return parts.join(", ");
}

function ReportActions() {
  const { notify } = useToast();
  const { preview, send } = useReportActions();
  return (
    <div className="mt-4">
      <p className="text-small text-gray-600">
        The report covers the last 24 hours and is sent from your connected Gmail. Save your
        settings first, then preview it or send it now.
      </p>
      <div className="mt-3 flex flex-wrap gap-2">
        <Button type="button" variant="secondary" isLoading={preview.isPending} onClick={() => preview.mutate(undefined, { onError: (e) => notify(apiErrorMessage(e, "Could not build the report."), "danger") })}>
          Preview report
        </Button>
        <Button
          type="button"
          variant="secondary"
          isLoading={send.isPending}
          onClick={() =>
            send.mutate(undefined, {
              onSuccess: (r) => notify(`Report sent to ${r.to}.`, "success"),
              onError: (e) => notify(apiErrorMessage(e, "The report was not sent."), "danger"),
            })
          }
        >
          Send it now
        </Button>
      </div>
      {preview.data ? (
        <div className="mt-4 overflow-hidden rounded-card border border-gray-200">
          <p className="border-b border-gray-200 bg-gray-50 px-3 py-2 text-small font-medium text-ink">
            {preview.data.subject}
          </p>
          <iframe
            title="Report preview"
            sandbox=""
            srcDoc={preview.data.html}
            className="h-[520px] w-full bg-white"
          />
        </div>
      ) : null}
    </div>
  );
}

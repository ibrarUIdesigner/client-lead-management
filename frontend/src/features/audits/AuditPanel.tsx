import { useEffect, useState } from "react";
import { Check, X } from "lucide-react";
import { Link, useNavigate } from "react-router-dom";

import { EmptyState } from "../../components/feedback/EmptyState";
import { useToast } from "../../components/feedback/useToast";
import { Badge } from "../../components/ui/Badge";
import { Button } from "../../components/ui/Button";
import { Card } from "../../components/ui/Card";
import { Skeleton } from "../../components/ui/Skeleton";
import { Spinner } from "../../components/ui/Spinner";
import { useLatestAudit, useRerunAudit, useStartAudit } from "../../hooks/useAudit";
import { apiErrorCode, apiErrorMessage } from "../../lib/apiError";
import { cn, focusRing } from "../../lib/cn";
import { formatWhen } from "../../lib/format";
import { screenshotUrl } from "../../services/audits";
import type { Audit } from "../../types/audit";

type AuditPanelProps = {
  leadId: string;
  websiteUrl: string | null;
};

const checks = [
  { key: "has_ssl", label: "HTTPS" },
  { key: "is_mobile_responsive", label: "Mobile" },
  { key: "has_clear_cta", label: "Call to action" },
  { key: "has_contact_form", label: "Contact form" },
  { key: "has_modern_navigation", label: "Navigation" },
  { key: "has_social_proof", label: "Social proof" },
] as const;

export function AuditPanel({ leadId, websiteUrl }: AuditPanelProps) {
  const navigate = useNavigate();
  const { notify } = useToast();
  const audit = useLatestAudit(leadId);
  const startAudit = useStartAudit(leadId);
  const rerunAudit = useRerunAudit(leadId);
  const missing = audit.isError && apiErrorCode(audit.error) === "AUDIT_NOT_FOUND";
  const running = audit.data?.status === "PENDING" || audit.data?.status === "RUNNING";
  const hasWebsite = Boolean(websiteUrl);

  const analyze = () => {
    startAudit.mutate(undefined, {
      onError: (error) => {
        notify(apiErrorMessage(error, "The website could not be analyzed."), "danger");
      },
    });
  };

  const retry = () => {
    if (!audit.data) {
      return;
    }
    if (!hasWebsite) {
      navigate(`/leads/${leadId}/edit`);
      return;
    }
    rerunAudit.mutate(audit.data.id, {
      onError: (error) => {
        notify(apiErrorMessage(error, "The website could not be analyzed."), "danger");
      },
    });
  };

  if (audit.isPending) {
    return (
      <div className="space-y-3" aria-busy="true">
        <Skeleton className="h-8 w-48" />
        <Skeleton className="h-40 w-full" />
      </div>
    );
  }

  if (audit.isError && !missing) {
    return (
      <div>
        <EmptyState
          title="The audit could not be loaded"
          description={apiErrorMessage(audit.error, "The audit could not be loaded.")}
          action={
            <Button
              variant="secondary"
              onClick={() => {
                void audit.refetch();
              }}
            >
              Retry
            </Button>
          }
        />
      </div>
    );
  }

  if (missing || !audit.data) {
    if (!hasWebsite) {
      return (
        <div>
          <EmptyState
            title="No website address on this lead"
            description="A full audit needs a public URL. Add the website on the lead, or record that none is listed so you can pitch a new site."
            action={
              <div className="flex flex-wrap gap-2">
                <Button
                  onClick={() => {
                    navigate(`/leads/${leadId}/edit`);
                  }}
                >
                  Add website URL
                </Button>
                <Button variant="secondary" onClick={analyze} isLoading={startAudit.isPending}>
                  Confirm no website
                </Button>
              </div>
            }
          />
        </div>
      );
    }

    return (
      <div>
        <EmptyState
          title="No website audit yet"
          description="Checks the homepage plus About, Contact, and a service page when they are linked."
          action={
            <Button onClick={analyze} isLoading={startAudit.isPending}>
              Analyze website
            </Button>
          }
        />
      </div>
    );
  }

  if (running && audit.data) {
    return <AnalyzingAudit url={audit.data.url ?? websiteUrl} startedAt={audit.data.created_at} />;
  }

  if (audit.data.status === "FAILED") {
    return (
      <div>
        <EmptyState
          title="The website could not be analyzed"
          description={audit.data.raw_analysis?.error || "Try the website again."}
          action={
            <Button onClick={retry} isLoading={rerunAudit.isPending}>
              {hasWebsite ? "Try again" : "Add website URL"}
            </Button>
          }
        />
      </div>
    );
  }

  return (
    <AuditResults
      audit={audit.data}
      leadId={leadId}
      hasWebsite={hasWebsite}
      onRetry={retry}
      retrying={rerunAudit.isPending}
      onCreateMockup={() => {
        navigate("/mockups");
      }}
    />
  );
}

const analysisStages = [
  {
    title: "Homepage",
    detail: "Open the public URL and read the page that customers see first.",
    at: 0,
  },
  {
    title: "Screenshots",
    detail: "Capture the desktop layout and the phone layout.",
    at: 12,
  },
  {
    title: "Speed and mobile",
    detail: "Measure loading, responsiveness, and real-visitor data when Chrome has it.",
    at: 28,
  },
  {
    title: "Linked pages",
    detail: "Follow About, Contact, and a service page when those links exist.",
    at: 50,
  },
  {
    title: "Scores and findings",
    detail: "Score performance, design, SEO, usability, and mobile, then list what to fix.",
    at: 75,
  },
];

function AnalyzingAudit({ url, startedAt }: { url: string | null; startedAt: string }) {
  const [now, setNow] = useState(() => Date.now());

  useEffect(() => {
    const timer = window.setInterval(() => {
      setNow(Date.now());
    }, 1000);
    return () => {
      window.clearInterval(timer);
    };
  }, []);

  const started = Date.parse(startedAt);
  const elapsed = Number.isNaN(started) ? 0 : Math.max(0, Math.floor((now - started) / 1000));
  const current = analysisStages.findLastIndex((stage) => elapsed >= stage.at);
  const active = current < 0 ? 0 : current;
  const progress = Math.min(92, Math.round((elapsed / 90) * 92));

  return (
    <Card className="shadow-sm" aria-live="polite">
      <div className="flex items-start justify-between gap-4">
        <div>
          <p className="text-caption font-semibold text-gray-500">Website audit</p>
          <h2 className="mt-1 text-h4 font-semibold text-ink">Analyzing the website</h2>
          <p className="mt-1 text-body text-gray-600">
            Homepage, screenshots, speed, linked pages, and scores run as one check. Results
            replace this view when the full audit is ready. That is usually one to two minutes.
          </p>
        </div>
        <span className="inline-flex size-10 shrink-0 items-center justify-center rounded-full bg-primary-50 text-primary-700">
          <Spinner />
        </span>
      </div>

      {url ? (
        <p className="mt-4 truncate text-small font-medium text-ink" title={url}>
          {url}
        </p>
      ) : null}

      <div className="mt-4">
        <div className="flex items-baseline justify-between gap-3 text-caption text-gray-500">
          <span>{formatElapsed(elapsed)} elapsed</span>
          <span>Estimate, not a finished percent</span>
        </div>
        <div className="mt-2 h-1.5 overflow-hidden rounded-full bg-gray-100">
          <div className="h-full rounded-full bg-primary" style={{ width: `${progress}%` }} />
        </div>
      </div>

      <ol className="mt-5 space-y-3">
        {analysisStages.map((stage, index) => {
          const state = index === active ? "now" : index < active ? "started" : "next";
          return (
            <li key={stage.title} className="flex gap-3">
              <span
                className={cn(
                  "mt-0.5 inline-flex size-6 shrink-0 items-center justify-center rounded-full text-caption font-bold",
                  state === "now" && "bg-primary text-white",
                  state === "started" && "bg-primary-50 text-primary-700",
                  state === "next" && "bg-gray-100 text-gray-500",
                )}
              >
                {index + 1}
              </span>
              <div className="min-w-0">
                <p className="text-body font-semibold text-ink">
                  {stage.title}
                  <span className="ml-2 text-caption font-medium text-gray-500">
                    {state === "now" ? "Checking now" : state === "started" ? "Underway" : "Next"}
                  </span>
                </p>
                <p className="mt-0.5 text-small text-gray-600">{stage.detail}</p>
              </div>
            </li>
          );
        })}
      </ol>
    </Card>
  );
}

function formatElapsed(totalSeconds: number): string {
  const minutes = Math.floor(totalSeconds / 60);
  const seconds = totalSeconds % 60;
  if (minutes <= 0) {
    return `${seconds}s`;
  }
  return `${minutes}m ${seconds.toString().padStart(2, "0")}s`;
}

function AuditResults({
  audit,
  leadId,
  hasWebsite,
  onRetry,
  retrying,
  onCreateMockup,
}: {
  audit: Audit;
  leadId: string;
  hasWebsite: boolean;
  onRetry: () => void;
  retrying: boolean;
  onCreateMockup: () => void;
}) {
  const analysis = audit.raw_analysis;
  const brand = analysis?.brand;
  const missingWebsite = !hasWebsite || isMissingWebsiteAudit(audit);
  const scores = [
    { label: "Performance", value: audit.performance_score },
    { label: "Mobile", value: audit.mobile_score },
    { label: "Design", value: audit.design_score },
    { label: "UX", value: audit.ux_score },
    { label: "SEO", value: audit.seo_score },
  ];

  return (
    <div className="space-y-4">
      {missingWebsite ? (
        <Card className="border-amber-200 bg-amber-50">
          <h2 className="text-h4 font-semibold text-amber-950">No URL to crawl</h2>
          <p className="mt-2 text-body text-amber-900">
            This result only confirms the lead has no website address on file. It did not open or
            score a live site. Add the URL to run a real audit.
          </p>
          <div className="mt-4">
            <Link
              to={`/leads/${leadId}/edit`}
              className={cn(
                "inline-flex h-10 items-center rounded-control bg-amber-900 px-4 text-body font-semibold text-white hover:bg-amber-950",
                focusRing,
              )}
            >
              Add website URL
            </Link>
          </div>
        </Card>
      ) : null}

      <Card className="shadow-sm">
        <div className="flex flex-col gap-4 sm:flex-row sm:items-start sm:justify-between">
          <div className="min-w-0 flex-1">
            <p className="text-caption font-semibold text-gray-500">Opportunity score</p>
            <p className="mt-1 text-h2 font-bold text-ink tabular-nums">
              {analysis?.opportunity_score ?? "—"}
            </p>
            <div className="mt-3 h-1.5 max-w-xs overflow-hidden rounded-full bg-gray-100">
              <div
                className={cn("h-full rounded-full", meterColor(analysis?.opportunity_score))}
                style={{ width: `${meterWidth(analysis?.opportunity_score)}%` }}
              />
            </div>
            <p className="mt-2 text-small text-gray-600">
              Higher means more reason to reach out. Checked {formatWhen(audit.completed_at)}.
            </p>
          </div>
          <div className="flex flex-wrap gap-2">
            {missingWebsite ? (
              <Button variant="secondary" onClick={onRetry}>
                Add website URL
              </Button>
            ) : (
              <Button variant="secondary" onClick={onRetry} isLoading={retrying}>
                Run again
              </Button>
            )}
            <Button onClick={onCreateMockup}>Create mockup</Button>
          </div>
        </div>
        {analysis?.opportunity_breakdown && analysis.opportunity_breakdown.length > 0 ? (
          <OpportunityBars items={analysis.opportunity_breakdown} />
        ) : (
          <p className="mt-4 text-body text-gray-600">No major website gaps were found.</p>
        )}
      </Card>

      {analysis?.report && analysis.report.length > 0 ? (
        <Card>
          <h2 className="text-h4 font-semibold text-ink">What to mention</h2>
          <p className="mt-2 text-small text-gray-600">
            {analysis.pages && analysis.pages.length > 0
              ? `The strongest checked issues from ${pageList(analysis.pages)}.`
              : "The strongest checked issues."}
          </p>
          <ol className="mt-4 space-y-3">
            {analysis.report.map((item) => (
              <li
                key={`${item.code}-${item.url}`}
                className="rounded-control border border-gray-200 p-4"
              >
                <p className="font-medium text-ink">{item.title}</p>
                <p className="mt-1 text-small text-gray-600">{item.detail}</p>
                {item.fix ? (
                  <p className="mt-3 rounded-control bg-primary-50 px-3 py-2 text-small text-primary-800">
                    Fix: {item.fix}
                  </p>
                ) : null}
                {item.url ? (
                  <a
                    href={item.url}
                    className="mt-2 block truncate text-caption text-primary-700"
                    target="_blank"
                    rel="noreferrer"
                  >
                    {item.url}
                  </a>
                ) : null}
              </li>
            ))}
          </ol>
          {analysis.field_data?.detail ? (
            <p className="mt-4 text-small text-gray-600">{analysis.field_data.detail}</p>
          ) : null}
        </Card>
      ) : null}

      <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-5">
        {scores.map((score) => (
          <Card key={score.label} className="shadow-sm">
            <div className="flex items-baseline justify-between gap-2">
              <p className="text-caption font-semibold text-gray-500">{score.label}</p>
              <p className="text-h4 font-semibold text-ink tabular-nums">{score.value ?? "—"}</p>
            </div>
            <div className="mt-3 h-1.5 overflow-hidden rounded-full bg-gray-100">
              <div
                className={cn("h-full rounded-full", meterColor(score.value))}
                style={{ width: `${meterWidth(score.value)}%` }}
              />
            </div>
          </Card>
        ))}
      </div>

      {analysis?.tools && analysis.tools.length > 0 ? (
        <Card>
          <h2 className="text-h4 font-semibold text-ink">Audit tools</h2>
          <ul className="mt-4 space-y-3">
            {analysis.tools.map((tool) => (
              <li
                key={tool.name}
                className="flex flex-col gap-1 sm:flex-row sm:items-baseline sm:gap-3"
              >
                <Badge tone={tool.status === "used" ? "green" : "orange"}>{tool.name}</Badge>
                <p className="text-small text-gray-600">{tool.detail}</p>
              </li>
            ))}
          </ul>
        </Card>
      ) : null}

      <Card>
        <h2 className="text-h4 font-semibold text-ink">Checks</h2>
        <ul className="mt-4 grid gap-2 sm:grid-cols-2">
          {checks.map((check) => {
            const passed = audit[check.key];
            const label = passed === null ? "Unknown" : passed ? "Yes" : "No";
            return (
              <li
                key={check.key}
                className="flex items-center justify-between gap-3 rounded-control border border-gray-200 px-3 py-2"
              >
                <span className="text-body text-ink">{check.label}</span>
                <span
                  className={cn(
                    "inline-flex items-center gap-1 text-small font-medium",
                    passed
                      ? "text-emerald-700"
                      : passed === false
                        ? "text-amber-800"
                        : "text-gray-500",
                  )}
                >
                  {passed ? <Check className="size-4" aria-hidden="true" /> : null}
                  {passed === false ? <X className="size-4" aria-hidden="true" /> : null}
                  {label}
                </span>
              </li>
            );
          })}
        </ul>
      </Card>

      {audit.has_desktop_screenshot || audit.has_mobile_screenshot ? (
        <div className="grid gap-4 lg:grid-cols-2">
          {audit.has_desktop_screenshot ? (
            <Screenshot auditId={audit.id} variant="desktop" label="Desktop" />
          ) : null}
          {audit.has_mobile_screenshot ? (
            <Screenshot auditId={audit.id} variant="mobile" label="Mobile" />
          ) : null}
        </div>
      ) : null}

      {audit.issues.length > 0 ? (
        <Card>
          <h2 className="text-h4 font-semibold text-ink">Issues</h2>
          <ul className="mt-4 space-y-3">
            {audit.issues.map((issue) => (
              <li key={issue.code} className="rounded-control border border-gray-200 px-4 py-3">
                <p className="font-medium text-ink">{issue.title}</p>
                <p className="mt-1 text-small text-gray-600">{issue.detail}</p>
              </li>
            ))}
          </ul>
        </Card>
      ) : null}

      {audit.recommendations.length > 0 ? (
        <Card>
          <h2 className="text-h4 font-semibold text-ink">Recommendations</h2>
          <ul className="mt-4 space-y-3">
            {audit.recommendations.map((item) => (
              <li key={item.code} className="rounded-control border border-gray-200 px-4 py-3">
                <p className="font-medium text-ink">{item.title}</p>
                <p className="mt-1 text-small text-gray-600">{item.detail}</p>
              </li>
            ))}
          </ul>
        </Card>
      ) : null}

      {brand?.brand_description || brand?.primary_color || brand?.font_primary ? (
        <Card>
          <h2 className="text-h4 font-semibold text-ink">Brand</h2>
          {brand.brand_description ? (
            <p className="mt-3 text-body text-gray-700">{brand.brand_description}</p>
          ) : null}
          <div className="mt-4 flex flex-wrap items-center gap-4">
            <ColorSwatch color={brand.primary_color} label="Primary" />
            <ColorSwatch color={brand.secondary_color} label="Text" />
            {brand.font_primary ? (
              <p className="text-small text-gray-600">Font: {brand.font_primary}</p>
            ) : null}
          </div>
        </Card>
      ) : null}
    </div>
  );
}

function isMissingWebsiteAudit(audit: Audit): boolean {
  return audit.issues.some((issue) => issue.code === "missing_website");
}

function OpportunityBars({ items }: { items: { code: string; label: string; points: number }[] }) {
  const max = Math.max(...items.map((item) => item.points), 1);

  return (
    <ul className="mt-5 space-y-3 border-t border-gray-100 pt-5">
      {items.map((item) => (
        <li key={item.code}>
          <div className="flex items-baseline justify-between gap-3 text-body text-ink">
            <span>{item.label}</span>
            <span className="font-medium tabular-nums">+{item.points}</span>
          </div>
          <div className="mt-1.5 h-1.5 overflow-hidden rounded-full bg-gray-100">
            <div
              className="h-full rounded-full bg-primary"
              style={{ width: `${Math.round((item.points / max) * 100)}%` }}
            />
          </div>
        </li>
      ))}
    </ul>
  );
}

function meterWidth(value: number | null | undefined): number {
  if (value == null) {
    return 0;
  }
  return Math.max(0, Math.min(100, value));
}

function meterColor(value: number | null | undefined): string {
  if (value == null) {
    return "bg-gray-200";
  }
  if (value >= 70) {
    return "bg-emerald-500";
  }
  if (value >= 40) {
    return "bg-amber-400";
  }
  return "bg-red-400";
}

function pageList(pages: { role: string }[]): string {
  const names = pages.map((page) => page.role.toLowerCase());
  if (names.length < 2) {
    return names[0] ?? "";
  }
  return `${names.slice(0, -1).join(", ")}, and ${names[names.length - 1]}`;
}

function Screenshot({
  auditId,
  variant,
  label,
}: {
  auditId: string;
  variant: "desktop" | "mobile";
  label: string;
}) {
  return (
    <Card>
      <h2 className="text-h4 font-semibold text-ink">{label}</h2>
      <img
        src={screenshotUrl(auditId, variant)}
        alt={`${label} screenshot of the website`}
        className="mt-4 max-h-80 w-full rounded-control border border-gray-200 object-contain object-top"
      />
    </Card>
  );
}

function ColorSwatch({ color, label }: { color?: string | null; label: string }) {
  if (!color || !isCssColor(color)) {
    return null;
  }

  return (
    <div className="flex items-center gap-2">
      <span
        className="size-6 rounded-control border border-gray-200"
        style={{ backgroundColor: color }}
        aria-hidden="true"
      />
      <span className="text-small text-gray-600">
        {label}: {color}
      </span>
    </div>
  );
}

function isCssColor(value: string): boolean {
  return (
    /^#(?:[0-9a-f]{3}|[0-9a-f]{6})$/i.test(value) ||
    /^rgba?\(\s*\d{1,3}\s*,\s*\d{1,3}\s*,\s*\d{1,3}(?:\s*,\s*(?:0|1|0?\.\d+))?\s*\)$/i.test(value)
  );
}

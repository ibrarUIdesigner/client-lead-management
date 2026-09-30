import { useNavigate } from "react-router-dom";

import { EmptyState } from "../../components/feedback/EmptyState";
import { useToast } from "../../components/feedback/useToast";
import { Badge } from "../../components/ui/Badge";
import { Button } from "../../components/ui/Button";
import { Card } from "../../components/ui/Card";
import { Skeleton } from "../../components/ui/Skeleton";
import { Spinner } from "../../components/ui/Spinner";
import { useLatestAudit, useRerunAudit, useStartAudit } from "../../hooks/useAudit";
import { apiErrorCode, apiErrorMessage } from "../../lib/apiError";
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
] as const;

export function AuditPanel({ leadId, websiteUrl }: AuditPanelProps) {
  const navigate = useNavigate();
  const { notify } = useToast();
  const audit = useLatestAudit(leadId);
  const startAudit = useStartAudit(leadId);
  const rerunAudit = useRerunAudit(leadId);
  const missing = audit.isError && apiErrorCode(audit.error) === "AUDIT_NOT_FOUND";
  const running = audit.data?.status === "PENDING" || audit.data?.status === "RUNNING";

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
    rerunAudit.mutate(audit.data.id, {
      onError: (error) => {
        notify(apiErrorMessage(error, "The website could not be analyzed."), "danger");
      },
    });
  };

  if (audit.isPending) {
    return (
      <div className="mt-6 space-y-3" aria-busy="true">
        <Skeleton className="h-8 w-48" />
        <Skeleton className="h-40 w-full" />
      </div>
    );
  }

  if (audit.isError && !missing) {
    return (
      <div className="mt-6">
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
    return (
      <div className="mt-6">
        <EmptyState
          title="No website audit yet"
          description={
            websiteUrl
              ? "Analyze the website to see what is worth improving."
              : "This lead has no website address. You can still record that as an opportunity."
          }
          action={
            <Button onClick={analyze} isLoading={startAudit.isPending}>
              Analyze website
            </Button>
          }
        />
      </div>
    );
  }

  if (running) {
    return (
      <Card className="mt-6">
        <div className="flex items-center gap-3" aria-live="polite">
          <Spinner />
          <div>
            <h2 className="text-h4 font-semibold text-ink">Analyzing the website</h2>
            <p className="mt-1 text-body text-gray-600">This usually takes less than a minute.</p>
          </div>
        </div>
      </Card>
    );
  }

  if (audit.data.status === "FAILED") {
    return (
      <div className="mt-6">
        <EmptyState
          title="The website could not be analyzed"
          description={audit.data.raw_analysis?.error || "Try the website again."}
          action={
            <Button onClick={retry} isLoading={rerunAudit.isPending}>
              Try again
            </Button>
          }
        />
      </div>
    );
  }

  return (
    <AuditResults
      audit={audit.data}
      onRetry={retry}
      retrying={rerunAudit.isPending}
      onCreateMockup={() => {
        navigate("/mockups");
      }}
    />
  );
}

function AuditResults({
  audit,
  onRetry,
  retrying,
  onCreateMockup,
}: {
  audit: Audit;
  onRetry: () => void;
  retrying: boolean;
  onCreateMockup: () => void;
}) {
  const analysis = audit.raw_analysis;
  const brand = analysis?.brand;
  const scores = [
    { label: "Performance", value: audit.performance_score },
    { label: "Mobile", value: audit.mobile_score },
    { label: "Design", value: audit.design_score },
    { label: "UX", value: audit.ux_score },
    { label: "SEO", value: audit.seo_score },
  ];

  return (
    <div className="mt-6 space-y-6">
      <Card>
        <div className="flex flex-col gap-4 sm:flex-row sm:items-start sm:justify-between">
          <div>
            <p className="text-caption font-semibold text-gray-500">Opportunity score</p>
            <p className="mt-1 text-h2 font-bold text-ink">{analysis?.opportunity_score ?? "—"}</p>
            <p className="mt-2 text-small text-gray-600">
              Higher means more reason to reach out. Checked {formatWhen(audit.completed_at)}.
            </p>
          </div>
          <div className="flex flex-wrap gap-2">
            <Button variant="secondary" onClick={onRetry} isLoading={retrying}>
              Run again
            </Button>
            <Button onClick={onCreateMockup}>Create mockup</Button>
          </div>
        </div>
        {analysis?.opportunity_breakdown && analysis.opportunity_breakdown.length > 0 ? (
          <ul className="mt-4 space-y-2">
            {analysis.opportunity_breakdown.map((item) => (
              <li key={item.code} className="flex items-center justify-between text-body text-ink">
                <span>{item.label}</span>
                <span className="font-medium">+{item.points}</span>
              </li>
            ))}
          </ul>
        ) : (
          <p className="mt-4 text-body text-gray-600">No major website gaps were found.</p>
        )}
      </Card>

      <div className="grid gap-3 sm:grid-cols-5">
        {scores.map((score) => (
          <Card key={score.label}>
            <p className="text-caption font-semibold text-gray-500">{score.label}</p>
            <p className="mt-2 text-h3 font-semibold text-ink">{score.value ?? "—"}</p>
          </Card>
        ))}
      </div>

      <Card>
        <h2 className="text-h4 font-semibold text-ink">Checks</h2>
        <ul className="mt-4 flex flex-wrap gap-2">
          {checks.map((check) => {
            const passed = audit[check.key];
            return (
              <li key={check.key}>
                <Badge tone={passed ? "green" : "orange"}>
                  {check.label}: {passed ? "Yes" : "No"}
                </Badge>
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
              <li key={issue.code}>
                <p className="font-medium text-ink">{issue.title}</p>
                <p className="text-small text-gray-600">{issue.detail}</p>
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
              <li key={item.code}>
                <p className="font-medium text-ink">{item.title}</p>
                <p className="text-small text-gray-600">{item.detail}</p>
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

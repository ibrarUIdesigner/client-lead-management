import { Link } from "react-router-dom";
import { ArrowRight } from "lucide-react";

import { Badge } from "../../components/ui/Badge";
import { Card } from "../../components/ui/Card";
import { useAutomation, useAutomationConfig } from "../../hooks/usePipeline";
import { cn, focusRing } from "../../lib/cn";

function ago(at: string, now: number): string {
  const minutes = Math.max(0, Math.round((now - new Date(at).getTime()) / 60_000));
  if (minutes < 1) return "just now";
  if (minutes < 60) return `${minutes} min ago`;
  const hours = Math.round(minutes / 60);
  return hours < 48 ? `${hours} h ago` : `${Math.round(hours / 24)} days ago`;
}

function Figure({ label, value, of }: { label: string; value: number; of?: number }) {
  return (
    <div className="min-w-0">
      <p className="text-h4 font-semibold leading-tight text-ink">
        {value}
        {of ? <span className="text-small font-normal text-gray-500"> / {of}</span> : null}
      </p>
      <p className="text-caption text-gray-600">{label}</p>
    </div>
  );
}

/** The automation at a glance, on the dashboard. Renders nothing until it has data. */
export function AutomationStrip() {
  const overview = useAutomation();
  const config = useAutomationConfig();
  if (!overview.data || !config.data) return null;

  const { discovery, outreach, last_tick: lastTick } = overview.data;
  const paused = config.data.paused;
  const now = overview.dataUpdatedAt;
  const stale = !lastTick || now - new Date(lastTick.at).getTime() > 45 * 60_000;
  const toReview = outreach.drafts_to_review;

  return (
    <Card className="p-4 sm:p-5">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <div className="flex flex-wrap items-center gap-2">
          <Badge tone={paused ? "orange" : stale ? "gray" : "green"}>
            {paused ? "Automation paused" : stale ? "Waiting for the scheduler" : "Automation running"}
          </Badge>
          <span className="text-small text-gray-600">
            {lastTick ? `Last run ${ago(lastTick.at, now)}` : "Has not run yet"}
          </span>
        </div>
        <Link
          to="/automation"
          className={cn(
            "inline-flex items-center gap-1 text-small font-medium text-primary hover:underline",
            focusRing,
          )}
        >
          Manage <ArrowRight className="size-3.5" aria-hidden />
        </Link>
      </div>

      <div className="mt-4 grid grid-cols-2 gap-4 sm:grid-cols-4">
        <Figure label="Leads found today" value={discovery.created_today} of={discovery.limit} />
        <Figure label="Emails written" value={outreach.drafted_today} of={outreach.daily_limit} />
        <Figure label="Sent today" value={outreach.sent_today} />
        <Link
          to="/approvals"
          className={cn(
            "-m-2 block rounded-control p-2 hover:bg-gray-50",
            toReview > 0 && "bg-amber-50 hover:bg-amber-100",
            focusRing,
          )}
        >
          <p className="text-h4 font-semibold leading-tight text-ink">{toReview}</p>
          <p className="text-caption text-gray-600">Drafts to approve</p>
        </Link>
      </div>
    </Card>
  );
}

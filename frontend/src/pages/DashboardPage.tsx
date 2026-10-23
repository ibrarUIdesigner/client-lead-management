import { useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import {
  ArrowRight,
  CalendarClock,
  CheckCircle2,
  ChevronRight,
  Compass,
  Flame,
  Mail,
  MapPin,
  Sparkles,
  TrendingUp,
  UserCheck,
  Users,
} from "lucide-react";

import { Button } from "../components/ui/Button";
import { Card } from "../components/ui/Card";
import { Skeleton } from "../components/ui/Skeleton";
import { followUpBucket } from "../features/followups/buckets";
import { useHealth } from "../hooks/useHealth";
import { useLeads } from "../hooks/useLeads";
import { useAnalytics, useFollowups, useMockups, useOutreachMessages } from "../hooks/useWorkspace";
import { cn, focusRing } from "../lib/cn";
import { getNextBestAction } from "../lib/leadWorkflow";

export function DashboardPage() {
  const navigate = useNavigate();
  const health = useHealth();
  const analytics = useAnalytics();
  const followups = useFollowups();
  const mockups = useMockups();
  const outreach = useOutreachMessages();

  // Fetch top leads sorted by opportunity score
  const topLeads = useLeads({
    limit: 15,
    sort: "lead_score",
    direction: "desc",
  });

  const allFollowups = followups.data ?? [];
  const dueFollowups = allFollowups
    .filter((item) => {
      const bucket = followUpBucket(item);
      return bucket === "overdue" || bucket === "today";
    })
    .sort((a, b) => a.scheduled_for.localeCompare(b.scheduled_for));

  const leadItems = topLeads.data?.items ?? [];

  // Compute greeting dynamically on mount
  const [greeting] = useState(() => {
    const h = new Date().getHours();
    return h < 12 ? "Good morning" : h < 18 ? "Good afternoon" : "Good evening";
  });

  // Compute key metric counts
  const data = analytics.data;
  const newLeadsCount =
    data?.by_status.find((s) => s.status === "NEW")?.count ?? 0;
  const hotLeadsCount = data?.high_scores ?? 0;
  const outreachCount = (data?.contacted ?? 0) + (data?.outreach_drafts ?? 0);
  const repliesCount = data?.replies ?? 0;
  const followupsDueCount = dueFollowups.length;
  const wonCount = data?.wins ?? 0;

  // Build Today's Priorities from live leads & followups
  type PriorityItem = {
    id: string;
    leadId: string;
    businessName: string;
    city?: string | null;
    score?: number | null;
    type: "followup_due" | "hot_uncontacted" | "draft_ready" | "reply_received" | "needs_audit";
    title: string;
    description: string;
    ctaLabel: string;
    actionUrl: string;
    tone: "orange" | "emerald" | "blue";
  };

  const priorities: PriorityItem[] = [];

  // 1. Follow-ups due today or overdue
  for (const f of dueFollowups.slice(0, 3)) {
    priorities.push({
      id: `f-${f.id}`,
      leadId: f.lead_id,
      businessName: f.business_name,
      city: f.city,
      type: "followup_due",
      title: "Follow-up due today",
      description: f.notes ? `Scheduled: ${f.notes}` : "Follow-up is due. Contact prospect to maintain momentum.",
      ctaLabel: "Send Follow-up",
      actionUrl: `/leads/${f.lead_id}?tab=outreach`,
      tone: "orange",
    });
  }

  // 2. Unread replies or REPLIED status
  const repliedLeads = leadItems.filter((l) => l.email_unread || l.lead_status === "REPLIED");
  for (const l of repliedLeads.slice(0, 2)) {
    if (!priorities.some((p) => p.leadId === l.id)) {
      priorities.push({
        id: `reply-${l.id}`,
        leadId: l.id,
        businessName: l.business_name,
        city: l.city,
        score: l.lead_score,
        type: "reply_received",
        title: "Reply received from prospect",
        description: "Prospect engaged with your outreach. Respond promptly while active.",
        ctaLabel: "Open Reply",
        actionUrl: `/leads/${l.id}?tab=outreach`,
        tone: "emerald",
      });
    }
  }

  // 3. Drafts ready for manual review
  const draftMessages = (outreach.data ?? []).filter((m) => m.status === "DRAFT" || m.status === "READY");
  for (const d of draftMessages.slice(0, 2)) {
    if (!priorities.some((p) => p.leadId === d.lead_id)) {
      priorities.push({
        id: `draft-${d.id}`,
        leadId: d.lead_id,
        businessName: d.business_name,
        type: "draft_ready",
        title: "AI draft ready for manual review",
        description: `Subject: "${d.subject || "Tailored website proposal"}". Review and send via Gmail.`,
        ctaLabel: "Review Draft",
        actionUrl: `/leads/${d.lead_id}?tab=outreach`,
        tone: "blue",
      });
    }
  }

  // 4. High Opportunity Score leads that need action
  const hotLeads = leadItems.filter(
    (l) =>
      (l.lead_score ?? 0) >= 60 &&
      l.lead_status !== "WON" &&
      l.lead_status !== "LOST" &&
      l.lead_status !== "DO_NOT_CONTACT" &&
      !l.last_contacted_at,
  );
  for (const l of hotLeads.slice(0, 3)) {
    if (!priorities.some((p) => p.leadId === l.id)) {
      priorities.push({
        id: `hot-${l.id}`,
        leadId: l.id,
        businessName: l.business_name,
        city: l.city,
        score: l.lead_score,
        type: "hot_uncontacted",
        title: `Opportunity Score: ${l.lead_score}/100`,
        description: l.website_url
          ? "High opportunity score with active website gaps. Research and pitch."
          : "Business has no website discovered. Strong pitch opening.",
        ctaLabel: "Open Lead",
        actionUrl: `/leads/${l.id}`,
        tone: "orange",
      });
    }
  }

  return (
    <div className="space-y-6">
      {/* Command Center Header */}
      <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <h1 className="text-h2 font-bold tracking-tight text-ink">
            {greeting}, Ibrar 👋
          </h1>
          <p className="mt-1 text-body text-gray-600">
            Here's what needs your attention today in your client acquisition workflow.
          </p>
        </div>
        <div className="flex items-center gap-2">
          <Button
            variant="secondary"
            size="sm"
            onClick={() => navigate("/discover")}
            className="gap-2"
          >
            <Compass className="size-4" />
            <span>Find Leads</span>
          </Button>
          <Button
            variant="secondary"
            size="sm"
            onClick={() => navigate("/analytics")}
          >
            Full Analytics
          </Button>
        </div>
      </div>

      {/* Key Metrics Row (Clickable Filters) */}
      <div className="grid grid-cols-2 gap-3 sm:grid-cols-3 xl:grid-cols-6">
        <MetricCard
          label="New Leads"
          count={newLeadsCount}
          detail="Awaiting review"
          to="/leads?lead_status=NEW"
          icon={Users}
        />
        <MetricCard
          label="Hot Leads"
          count={hotLeadsCount}
          detail="Score 70+ to pitch"
          to="/leads?min_score=70"
          icon={Flame}
          tone="orange"
        />
        <MetricCard
          label="Outreach"
          count={outreachCount}
          detail="Drafted & sent"
          to="/outreach"
          icon={Mail}
        />
        <MetricCard
          label="Replies"
          count={repliesCount}
          detail="Prospect responses"
          to="/leads?lead_status=REPLIED"
          icon={TrendingUp}
          tone="emerald"
        />
        <MetricCard
          label="Follow-ups"
          count={followupsDueCount}
          detail="Due today / overdue"
          to="/follow-ups"
          icon={CalendarClock}
          tone={followupsDueCount > 0 ? "orange" : undefined}
        />
        <MetricCard
          label="Won"
          count={wonCount}
          detail="Closed clients"
          to="/leads?lead_status=WON"
          icon={UserCheck}
          tone="emerald"
        />
      </div>

      {/* Today's Priorities Section */}
      <section className="space-y-3">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            <Flame className="size-5 text-orange-600" />
            <h2 className="text-h4 font-bold text-ink">Today's Priorities</h2>
            <span className="rounded-full bg-orange-100 px-2 py-0.5 text-caption font-bold text-orange-800">
              {priorities.length} Action Items
            </span>
          </div>
          <span className="text-caption text-gray-500 hidden sm:inline">
            Ranked by immediate deal impact
          </span>
        </div>

        {topLeads.isPending ? (
          <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-3">
            <Skeleton className="h-36" />
            <Skeleton className="h-36" />
            <Skeleton className="h-36" />
          </div>
        ) : priorities.length === 0 ? (
          <Card className="p-8 text-center bg-gray-50/70 border-dashed">
            <CheckCircle2 className="size-8 mx-auto text-emerald-600" />
            <h3 className="mt-2 text-body font-semibold text-ink">You're all caught up!</h3>
            <p className="mt-1 text-small text-gray-600 max-w-md mx-auto">
              No overdue follow-ups or unread replies today. Discover new local businesses to qualify and audit.
            </p>
            <Button
              variant="primary"
              className="mt-4 h-9 px-4 text-small"
              onClick={() => navigate("/discover")}
            >
              Discover New Leads
            </Button>
          </Card>
        ) : (
          <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-3">
            {priorities.map((item) => (
              <Card
                key={item.id}
                className={cn(
                  "flex flex-col justify-between border-l-4 p-4 transition-all hover:border-gray-300 hover:shadow-xs",
                  item.tone === "orange"
                    ? "border-l-amber-500"
                    : item.tone === "emerald"
                    ? "border-l-emerald-500"
                    : "border-l-primary-500",
                )}
              >
                <div>
                  <div className="flex items-start justify-between gap-2">
                    <span className="text-[11px] font-bold uppercase tracking-wider text-gray-500">
                      {item.title}
                    </span>
                    {item.score ? (
                      <span className="inline-flex items-center gap-0.5 rounded-full bg-orange-50 px-2 py-0.5 text-caption font-bold text-orange-700 ring-1 ring-inset ring-orange-500/20">
                        <Flame className="size-3" />
                        {item.score}
                      </span>
                    ) : null}
                  </div>
                  <h3 className="mt-1.5 text-body-lg font-bold text-ink truncate">
                    {item.businessName}
                  </h3>
                  {item.city ? (
                    <p className="mt-0.5 flex items-center gap-1 text-caption text-gray-500">
                      <MapPin className="size-3" />
                      {item.city}
                    </p>
                  ) : null}
                  <p className="mt-2 text-small text-gray-600 line-clamp-2 leading-relaxed">
                    {item.description}
                  </p>
                </div>

                <div className="mt-4 flex items-center justify-between border-t border-gray-100 pt-3">
                  <Button
                    variant="ghost"
                    size="sm"
                    className="text-gray-600 px-2"
                    onClick={() => navigate(`/leads/${item.leadId}`)}
                  >
                    Open Lead
                  </Button>
                  <Button
                    variant={item.tone === "orange" ? "primary" : "secondary"}
                    size="sm"
                    className="gap-1.5 font-medium"
                    onClick={() => navigate(item.actionUrl)}
                  >
                    <span>{item.ctaLabel}</span>
                    <ArrowRight className="size-3.5" />
                  </Button>
                </div>
              </Card>
            ))}
          </div>
        )}
      </section>

      {/* Next Best Actions Workspace */}
      <section className="space-y-3">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            <Sparkles className="size-5 text-primary-600" />
            <h2 className="text-h4 font-bold text-ink">Next Best Actions Across Prospects</h2>
          </div>
          <Link
            to="/leads"
            className="text-small font-medium text-primary-700 hover:underline flex items-center gap-1"
          >
            <span>View All Leads</span>
            <ChevronRight className="size-4" />
          </Link>
        </div>

        <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
          {leadItems.slice(0, 3).map((lead) => {
            const nba = getNextBestAction(lead, {
              mockups: mockups.data,
              outreach: outreach.data,
              followups: followups.data,
            });

            return (
              <Card key={lead.id} className="p-4 shadow-sm flex flex-col justify-between">
                <div>
                  <div className="flex items-center justify-between gap-2">
                    <span className="text-caption font-bold uppercase tracking-wider text-primary-700">
                      {nba.badge}
                    </span>
                    {lead.lead_score ? (
                      <span className="inline-flex items-center gap-1 rounded-full bg-orange-50 px-2 py-0.5 text-caption font-bold text-orange-700">
                        <Flame className="size-3" />
                        {lead.lead_score}
                      </span>
                    ) : null}
                  </div>
                  <Link
                    to={`/leads/${lead.id}`}
                    className="mt-1.5 block text-body font-bold text-ink hover:text-primary-700 truncate"
                  >
                    {lead.business_name}
                  </Link>
                  <p className="text-caption text-gray-500">
                    {[lead.industry, lead.city].filter(Boolean).join(" · ") || "Local Business"}
                  </p>
                  <p className="mt-2 text-small text-gray-600 line-clamp-2">
                    {nba.reason}
                  </p>
                </div>

                <div className="mt-4 pt-3 border-t border-gray-100 flex items-center justify-between">
                  <span className="text-caption font-medium text-gray-500">
                    Next: <strong className="text-ink">{nba.action}</strong>
                  </span>
                  <Button
                    variant="secondary"
                    size="sm"
                    className="font-semibold px-2.5"
                    onClick={() => navigate(`/leads/${lead.id}?tab=${nba.targetTab}`)}
                  >
                    {nba.ctaLabel}
                  </Button>
                </div>
              </Card>
            );
          })}
        </div>
      </section>

      {/* Quick Acquisition Pipeline Overview */}
      <section className="grid gap-4 lg:grid-cols-3">
        {/* Acquisition Stage Progress */}
        <Card className="lg:col-span-2 p-5 shadow-2xs">
          <div className="flex items-center justify-between border-b border-gray-100 pb-3">
            <div>
              <h3 className="text-h4 font-bold text-ink">Acquisition Funnel</h3>
              <p className="text-caption text-gray-500">Prospect distribution across acquisition stages</p>
            </div>
            <Button
              variant="ghost"
              size="sm"
              onClick={() => navigate("/pipeline")}
              className="text-primary-700 gap-1 px-2"
            >
              <span>Open Pipeline</span>
              <ArrowRight className="size-3.5" />
            </Button>
          </div>

          <div className="mt-4 grid grid-cols-2 sm:grid-cols-4 gap-3">
            <StageBox
              label="Qualified"
              count={data?.by_status.find((s) => s.status === "QUALIFIED")?.count ?? 0}
              desc="Ready to audit"
            />
            <StageBox
              label="Audited"
              count={data?.audits_completed ?? 0}
              desc="Gaps uncovered"
            />
            <StageBox
              label="Mockup Ready"
              count={data?.mockups_ready ?? 0}
              desc="Visual pitches"
            />
            <StageBox
              label="Contacted"
              count={data?.contacted ?? 0}
              desc="Emails delivered"
            />
          </div>
        </Card>

        {/* Integration & Tools Status */}
        <Card className="p-5 shadow-sm">
          <div className="flex items-center justify-between border-b border-gray-100 pb-3">
            <h3 className="text-h4 font-bold text-ink">Engine Status</h3>
            <Link to="/settings" className="text-caption text-primary-700 hover:underline">
              Settings
            </Link>
          </div>
          <div className="mt-3 space-y-2.5">
            <IntegrationLine
              name="Gemini 2.5 Flash"
              role="Outreach & Synthesis"
              ready={health.data?.database === "ok"}
            />
            <IntegrationLine
              name="Tavily & Exa"
              role="Deep Research & Sources"
              ready={true}
            />
            <IntegrationLine
              name="Gmail Integration"
              role="Draft & Direct Delivery"
              ready={health.data?.email_drafts !== "unconfigured"}
            />
            <IntegrationLine
              name="PageSpeed & Chrome"
              role="Website Audit Engine"
              ready={true}
            />
          </div>
        </Card>
      </section>
    </div>
  );
}

function MetricCard({
  label,
  count,
  detail,
  to,
  icon: Icon,
  tone,
}: {
  label: string;
  count: number;
  detail: string;
  to: string;
  icon: any;
  tone?: "orange" | "emerald";
}) {
  const navigate = useNavigate();

  return (
    <button
      type="button"
      onClick={() => navigate(to)}
      className={cn(
        "group flex flex-col justify-between rounded-card border border-gray-200/90 bg-white p-4 text-left shadow-2xs transition-all hover:border-primary-300 hover:shadow-xs cursor-pointer",
        focusRing,
      )}
    >
      <div className="flex items-center justify-between w-full">
        <span className="text-[12px] font-semibold text-gray-500 group-hover:text-primary-700 transition-colors">
          {label}
        </span>
        <div
          className={cn(
            "flex size-7.5 items-center justify-center rounded-lg border border-gray-100 bg-gray-50 text-gray-400 group-hover:border-primary-200 group-hover:bg-primary-50 group-hover:text-primary-600 transition-colors",
            tone === "orange" && "text-orange-500 bg-orange-50/50 border-orange-100",
            tone === "emerald" && "text-emerald-600 bg-emerald-50/50 border-emerald-100",
          )}
        >
          <Icon className="size-4" />
        </div>
      </div>
      <div className="mt-3">
        <p className="text-2xl font-bold tracking-tight tabular-nums text-ink">{count}</p>
        <p className="mt-0.5 text-caption text-gray-400 truncate">{detail}</p>
      </div>
    </button>
  );
}

function StageBox({ label, count, desc }: { label: string; count: number; desc: string }) {
  return (
    <div className="rounded-xl border border-gray-200/70 bg-gray-50/50 p-3.5 text-center transition-colors">
      <span className="text-caption font-semibold text-gray-500">{label}</span>
      <p className="mt-1 text-h3 font-bold text-ink tabular-nums">{count}</p>
      <span className="text-[11px] text-gray-400">{desc}</span>
    </div>
  );
}

function IntegrationLine({ name, role, ready }: { name: string; role: string; ready: boolean }) {
  return (
    <div className="flex items-center justify-between rounded-lg border border-gray-100 bg-gray-50/50 p-2.5 transition-colors">
      <div>
        <p className="text-small font-semibold text-ink">{name}</p>
        <p className="text-[11px] text-gray-500">{role}</p>
      </div>
      <span
        className={cn(
          "inline-flex items-center gap-1.5 rounded-full px-2.5 py-0.5 text-[11px] font-semibold",
          ready
            ? "bg-emerald-50 text-emerald-700 ring-1 ring-inset ring-emerald-500/20"
            : "bg-gray-100 text-gray-600 ring-1 ring-inset ring-gray-400/20",
        )}
      >
        <span
          className={cn(
            "size-1.5 rounded-full",
            ready ? "bg-emerald-500 animate-pulse" : "bg-gray-400",
          )}
        />
        {ready ? "Active" : "Ready"}
      </span>
    </div>
  );
}

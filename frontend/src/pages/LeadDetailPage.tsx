import {
  ArrowLeft,
  CalendarClock,
  CheckCircle2,
  CircleDot,
  Flame,
  Globe,
  Images,
  Mail,
  MapPin,
  Phone,
  RefreshCw,
  Sparkles,
  Tag,
  Target,
} from "lucide-react";
import { useState, useEffect, type ReactNode } from "react";
import { useNavigate, useParams, useSearchParams } from "react-router-dom";

import { EmptyState } from "../components/feedback/EmptyState";
import { LoadingState } from "../components/feedback/LoadingState";
import { OfflineState } from "../components/feedback/OfflineState";
import { useToast } from "../components/feedback/useToast";
import { Badge, StatusBadge } from "../components/ui/Badge";
import { Button } from "../components/ui/Button";
import { Card } from "../components/ui/Card";
import { ConfirmDialog } from "../components/ui/ConfirmDialog";
import { Tabs } from "../components/ui/Tabs";
import { AuditPanel } from "../features/audits/AuditPanel";
import { ConversationPanel } from "../features/gmail/ConversationPanel";
import { GmailComposer } from "../features/gmail/GmailComposer";
import { LeadJourney } from "../features/leads/LeadJourney";
import { LeadResearchSection } from "../features/leads/LeadResearchSection";
import { NextBestActionBanner } from "../features/leads/NextBestActionBanner";
import { MockupGallery } from "../features/mockups/MockupGallery";
import { MessageList } from "../features/outreach/MessageList";
import { OutreachComposer } from "../features/outreach/OutreachComposer";
import { useLatestAudit } from "../hooks/useAudit";
import { useDeleteLead, useLead } from "../hooks/useLeads";
import { useOnline } from "../hooks/useOnline";
import { useLeadResearch } from "../hooks/useResearch";
import { useFollowups, useMockups, useOutreachMessages } from "../hooks/useWorkspace";
import { apiErrorCode, apiErrorMessage, isOfflineError } from "../lib/apiError";
import { cn, focusRing } from "../lib/cn";
import { formatWhen } from "../lib/format";
import {
  getLeadJourneySteps,
  getNextBestAction,
  getOpportunitySummary,
} from "../lib/leadWorkflow";
import type { Activity, LeadDetail } from "../types/lead";

function BackToLeads() {
  const navigate = useNavigate();

  return (
    <Button
      variant="ghost"
      className="-ml-3 mb-4 h-8 px-2 text-small text-gray-600"
      onClick={() => {
        navigate("/leads");
      }}
    >
      <ArrowLeft className="size-4 mr-1" aria-hidden="true" />
      Back to leads
    </Button>
  );
}

export function LeadDetailPage() {
  const { leadId = "" } = useParams();
  const navigate = useNavigate();
  const online = useOnline();
  const lead = useLead(leadId);

  if (!online && (lead.isPending || lead.isError)) {
    return (
      <>
        <BackToLeads />
        <OfflineState
          onRetry={() => {
            void lead.refetch();
          }}
        />
      </>
    );
  }

  if (lead.isPending) {
    return (
      <div>
        <BackToLeads />
        <LoadingState label="Loading lead" />
      </div>
    );
  }

  if (lead.isError && apiErrorCode(lead.error) === "LEAD_NOT_FOUND") {
    return (
      <EmptyState
        title="This lead does not exist"
        description="It may have been deleted."
        action={
          <Button
            onClick={() => {
              navigate("/leads");
            }}
          >
            Back to leads
          </Button>
        }
      />
    );
  }

  if (lead.isError && isOfflineError(lead.error)) {
    return (
      <>
        <BackToLeads />
        <OfflineState
          onRetry={() => {
            void lead.refetch();
          }}
        />
      </>
    );
  }

  if (lead.isError || !lead.data) {
    return (
      <>
        <BackToLeads />
        <EmptyState
          title="This lead could not be loaded"
          description={apiErrorMessage(lead.error, "The lead could not be loaded.")}
          action={
            <Button
              variant="secondary"
              onClick={() => {
                void lead.refetch();
              }}
            >
              Retry
            </Button>
          }
        />
      </>
    );
  }

  return <LeadDetailView lead={lead.data} />;
}

function LeadDetailView({ lead }: { lead: LeadDetail }) {
  const navigate = useNavigate();
  const [searchParams, setSearchParams] = useSearchParams();
  const { notify } = useToast();
  const removeLead = useDeleteLead();

  // Queries for surrounding workflow artifacts
  const auditQuery = useLatestAudit(lead.id);
  const researchQuery = useLeadResearch(lead.id);
  const mockupsQuery = useMockups(lead.id);
  const outreachQuery = useOutreachMessages(lead.id);
  const followupsQuery = useFollowups();

  const audit = auditQuery.data;
  const research = researchQuery.data;
  const mockups = mockupsQuery.data ?? [];
  const outreach = outreachQuery.data ?? [];
  const followups = (followupsQuery.data ?? []).filter((f) => f.lead_id === lead.id);

  // Tab synchronization with URL query param `?tab=...`
  const initialTab = searchParams.get("tab") || "overview";
  const [activeTab, setActiveTab] = useState(initialTab);
  const [confirming, setConfirming] = useState(false);
  const [outreachFocus, setOutreachFocus] = useState<string | null>(null);

  useEffect(() => {
    const tabParam = searchParams.get("tab");
    if (tabParam && tabParam !== activeTab) {
      setActiveTab(tabParam);
    }
  }, [searchParams]);

  const handleSelectTab = (tabId: string) => {
    setActiveTab(tabId);
    setSearchParams({ tab: tabId });
  };

  const remove = () => {
    removeLead.mutate(lead.id, {
      onSuccess: () => {
        notify("Lead deleted.", "success");
        navigate("/leads");
      },
      onError: (error) => {
        notify(apiErrorMessage(error, "Could not delete the lead."), "danger");
      },
    });
  };

  // Compute Next Best Action & Acquisition Journey
  const nba = getNextBestAction(lead, {
    audit,
    research,
    mockups,
    outreach,
    followups,
  });

  const steps = getLeadJourneySteps(lead, {
    audit,
    research,
    mockups,
    outreach,
  });

  const opportunitySummary = getOpportunitySummary(lead, audit, research);

  const place = [lead.city, lead.country].filter(Boolean).join(", ");
  const score = lead.lead_score ?? audit?.raw_analysis?.opportunity_score ?? null;

  return (
    <div className="space-y-4">
      <BackToLeads />

      {/* Main Lead Header */}
      <div className="flex flex-col gap-4 rounded-card border border-gray-200 bg-white p-5 shadow-2xs lg:flex-row lg:items-center lg:justify-between">
        <div>
          <div className="flex flex-wrap items-center gap-2">
            <h1 className="text-h2 font-bold tracking-tight text-ink">
              {lead.business_name}
            </h1>
            {lead.email_unread ? <Badge tone="orange">Unread reply</Badge> : null}
            {lead.do_not_contact ? <Badge tone="red">Do not contact</Badge> : null}
            <StatusBadge status={lead.lead_status} />
          </div>

          <div className="mt-1 flex flex-wrap items-center gap-3 text-small text-gray-600">
            {lead.industry ? <span className="font-medium text-ink">{lead.industry}</span> : null}
            {place ? (
              <span className="flex items-center gap-1">
                <MapPin className="size-3.5 text-gray-400" />
                {place}
              </span>
            ) : null}
            {lead.website_url ? (
              <a
                href={lead.website_url}
                target="_blank"
                rel="noreferrer"
                className="flex items-center gap-1 text-primary-700 hover:underline"
              >
                <Globe className="size-3.5" />
                <span>{lead.website_url.replace(/^https?:\/\//, "")}</span>
              </a>
            ) : (
              <span className="rounded bg-amber-50 px-2 py-0.5 text-caption font-medium text-amber-800">
                No website listed
              </span>
            )}
            {score !== null ? (
              <span
                className="inline-flex items-center gap-1 rounded-full bg-orange-50 px-2.5 py-0.5 text-caption font-bold text-orange-700"
                title="AI / heuristic opportunity score"
              >
                <Flame className="size-3.5 text-orange-600" />
                Score: {score}/100
              </span>
            ) : null}
          </div>
        </div>

        {/* Primary Acquisition Workflow Actions */}
        <div className="flex flex-wrap items-center gap-2">
          <Button
            variant="secondary"
            className="h-9 px-3 text-small"
            onClick={() => handleSelectTab("audit")}
          >
            <Globe className="size-4 mr-1 text-gray-500" />
            Audit
          </Button>
          <Button
            variant="secondary"
            className="h-9 px-3 text-small"
            onClick={() => handleSelectTab("research")}
          >
            <Sparkles className="size-4 mr-1 text-primary-600" />
            Research
          </Button>
          <Button
            variant="secondary"
            className="h-9 px-3 text-small"
            onClick={() => handleSelectTab("mockups")}
          >
            <Images className="size-4 mr-1 text-purple-600" />
            Mockup
          </Button>
          <Button
            variant="primary"
            className="h-9 px-3 text-small"
            onClick={() => handleSelectTab("outreach")}
          >
            <Mail className="size-4 mr-1" />
            Outreach
          </Button>
          <Button
            variant="ghost"
            className="h-9 px-2 text-small text-gray-500 hover:text-ink"
            onClick={() => navigate(`/leads/${lead.id}/edit`)}
          >
            Edit
          </Button>
          <Button
            variant="ghost"
            className="h-9 px-2 text-small text-gray-500 hover:text-danger"
            onClick={() => setConfirming(true)}
          >
            Delete
          </Button>
        </div>
      </div>

      {/* Visual Acquisition Journey Bar (Section 13) */}
      <LeadJourney steps={steps} onSelectTab={handleSelectTab} />

      {/* Primary Workspace Tabs: Overview | Audit | Research | Mockup | Outreach | Activity */}
      <Tabs
        label="Lead acquisition workspace"
        value={activeTab}
        onValueChange={handleSelectTab}
        tabs={[
          {
            id: "overview",
            label: "Overview",
            content: (
              <Overview
                lead={lead}
                audit={audit}
                research={research}
                mockups={mockups}
                outreach={outreach}
                followups={followups}
                nba={nba}
                opportunitySummary={opportunitySummary}
                onSelectTab={handleSelectTab}
              />
            ),
          },
          {
            id: "audit",
            label: "Audit",
            content: <AuditPanel leadId={lead.id} websiteUrl={lead.website_url} />,
          },
          {
            id: "research",
            label: "Research",
            content: <LeadResearchSection lead={lead} onSelectTab={handleSelectTab} />,
          },
          {
            id: "mockups",
            label: "Mockups",
            count: mockups.length > 0 ? mockups.length : undefined,
            content: <MockupGallery leadId={lead.id} />,
          },
          {
            id: "outreach",
            label: "Outreach",
            count: outreach.length > 0 ? outreach.length : undefined,
            content: (
              <div className="space-y-4">
                <OutreachComposer
                  leadId={lead.id}
                  email={lead.email}
                  hasWebsite={Boolean(lead.website_url) && lead.website_status !== "missing"}
                  onCreated={setOutreachFocus}
                />
                <Card className="overflow-hidden p-0 shadow-sm">
                  <div className="grid min-w-0 lg:grid-cols-2 lg:divide-x lg:divide-gray-100">
                    <section className="min-w-0 p-4 sm:p-5">
                      <h2 className="text-h4 font-semibold text-ink">Messages</h2>
                      <p className="mt-1 text-small text-gray-600">
                        Drafts from the generator land here for manual review.
                      </p>
                      <div className="mt-3">
                        <MessageList leadId={lead.id} focusId={outreachFocus} expandFirstDraft />
                      </div>
                    </section>
                    <section className="min-w-0 border-t border-gray-100 p-4 sm:p-5 lg:border-t-0">
                      <ConversationPanel leadId={lead.id} />
                    </section>
                  </div>
                </Card>
                <GmailComposer leadId={lead.id} defaultTo={lead.email} />
              </div>
            ),
          },
          {
            id: "activity",
            label: "Activity",
            count: lead.activities.length,
            content: <ActivityList lead={lead} />,
          },
        ]}
      />

      <ConfirmDialog
        open={confirming}
        title="Delete this lead?"
        description="Notes and activity for this lead will be removed permanently."
        confirmLabel="Delete lead"
        isLoading={removeLead.isPending}
        onConfirm={remove}
        onClose={() => {
          if (!removeLead.isPending) {
            setConfirming(false);
          }
        }}
      />
    </div>
  );
}

const websiteStatusLabels: Record<string, string> = {
  present: "Has a website",
  missing: "No website",
  social_only: "Social only",
  pending: "Audit pending",
  analyzed: "Audited",
  failed: "Audit failed",
};

function Overview({
  lead,
  audit,
  research,
  mockups,
  outreach,
  followups,
  nba,
  opportunitySummary,
  onSelectTab,
}: {
  lead: LeadDetail;
  audit?: any;
  research?: any;
  mockups: any[];
  outreach: any[];
  followups: any[];
  nba: any;
  opportunitySummary: { title: string; bullets: string[]; highlightScore: number | null };
  onSelectTab: (tabId: string) => void;
}) {
  const place = [lead.city, lead.country].filter(Boolean).join(", ");
  const socials = [
    linkItem("LinkedIn", lead.linkedin_url),
    linkItem("Instagram", lead.instagram_url),
    linkItem("Facebook", lead.facebook_url),
    linkItem("Google Maps", lead.google_maps_url),
  ].filter((item) => item !== null);
  const followUpOverdue = isPast(lead.next_followup_at);

  return (
    <div className="space-y-4">
      {/* 1. Next Best Action (Section 14 & 47) */}
      <NextBestActionBanner
        action={nba}
        onExecute={() => onSelectTab(nba.targetTab)}
      />

      {/* 2. Opportunity Summary (Section 14 & 21) */}
      <Card className="border-primary-100 bg-gradient-to-r from-primary-50/40 via-white to-white p-5 shadow-sm">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            <Target className="size-4 text-primary-600" />
            <h3 className="text-h4 font-bold text-ink">{opportunitySummary.title}</h3>
          </div>
          <span className="text-[11px] text-gray-500 uppercase tracking-wider font-semibold">
            Opportunity Intelligence
          </span>
        </div>
        <p className="mt-1 text-small text-gray-600">
          Synthesized from website health, research signals, and competitive positioning:
        </p>
        <ul className="mt-3 space-y-2">
          {opportunitySummary.bullets.map((bullet, idx) => (
            <li key={idx} className="flex items-start gap-2 text-small text-gray-800">
              <CheckCircle2 className="size-4 shrink-0 text-emerald-600 mt-0.5" />
              <span>{bullet}</span>
            </li>
          ))}
        </ul>
      </Card>

      {/* 3. Current Situation Grid (Section 14) */}
      <div>
        <h4 className="text-caption font-bold uppercase tracking-wider text-gray-500 mb-2">
          Current Acquisition Situation
        </h4>
        <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-3 2xl:grid-cols-6">
          <SummaryCard
            label="Opportunity Score"
            value={lead.lead_score ? `${lead.lead_score}/100` : "Pending"}
            detail="AI / heuristic estimate"
          />
          <SummaryCard
            label="Website Health"
            value={
              audit?.performance_score !== undefined && audit?.performance_score !== null
                ? `${audit.performance_score}/100`
                : websiteStatusLabels[lead.website_status ?? ""] ?? lead.website_status ?? "Not Audited"
            }
            detail={
              audit?.status === "COMPLETED"
                ? "Full audit complete"
                : lead.website_url
                ? "Click Audit tab to run"
                : "No website discovered"
            }
          />
          <SummaryCard
            label="Research Intelligence"
            value={
              research?.status === "COMPLETED"
                ? "Completed"
                : research?.status === "RUNNING"
                ? "Running..."
                : "Not Run"
            }
            detail={
              research?.status === "COMPLETED"
                ? `${research.sources?.length || 0} sources verified`
                : "Tavily & Exa deep search"
            }
          />
          <SummaryCard
            label="Homepage Mockup"
            value={mockups.length > 0 ? `${mockups.length} Version(s)` : "None"}
            detail={mockups.some((m) => m.status === "READY") ? "Ready to pitch" : "Create in Mockup tab"}
          />
          <SummaryCard
            label="Outreach Status"
            value={
              lead.last_contacted_at
                ? "Contacted"
                : outreach.length > 0
                ? `${outreach.length} Draft(s)`
                : "Not Sent"
            }
            detail={lead.last_contacted_at ? formatWhen(lead.last_contacted_at) : "Awaiting draft"}
          />
          <SummaryCard
            label="Follow-up"
            value={lead.next_followup_at ? formatWhen(lead.next_followup_at) : followups.length > 0 ? "Scheduled" : "None Set"}
            emphasis={followUpOverdue}
            detail={followUpOverdue ? "Overdue" : followups.length > 0 ? `${followups.length} scheduled` : "No follow-up set"}
          />
        </div>
      </div>

      {/* 4. Business Snapshot & Details (Section 14) */}
      <div className="grid gap-4 lg:grid-cols-5">
        <Card className="shadow-sm lg:col-span-3">
          <h2 className="text-h4 font-bold text-ink">How to Reach Them</h2>
          <dl className="mt-2">
            <Fact icon={<Mail className="size-4" aria-hidden="true" />} label="Email">
              {lead.email ? (
                <a href={`mailto:${lead.email}`} className={cn("break-all text-primary-700 font-medium", focusRing)}>
                  {lead.email}
                </a>
              ) : (
                <span className="text-gray-400">No email on file</span>
              )}
            </Fact>
            <Fact icon={<Phone className="size-4" aria-hidden="true" />} label="Phone">
              {lead.phone ? (
                <a href={`tel:${lead.phone}`} className={cn("text-primary-700 font-medium", focusRing)}>
                  {lead.phone}
                </a>
              ) : (
                <span className="text-gray-400">No phone on file</span>
              )}
            </Fact>
            <Fact icon={<Globe className="size-4" aria-hidden="true" />} label="Website">
              {lead.website_url ? (
                <a
                  href={lead.website_url}
                  target="_blank"
                  rel="noreferrer"
                  className={cn("break-all text-primary-700 font-medium", focusRing)}
                >
                  {lead.website_url}
                </a>
              ) : (
                <span className="text-gray-400">No website discovered</span>
              )}
            </Fact>
            <Fact icon={<MapPin className="size-4" aria-hidden="true" />} label="Location">
              {place || "—"}
            </Fact>
          </dl>
          {socials.length > 0 ? (
            <div className="mt-4 flex flex-wrap gap-2 border-t border-gray-100 pt-4">
              {socials.map((item) => (
                <a
                  key={item.label}
                  href={item.href}
                  target="_blank"
                  rel="noreferrer"
                  className={cn(
                    "rounded-full border border-gray-200 px-3 py-1 text-small font-medium text-ink hover:bg-gray-50",
                    focusRing,
                  )}
                >
                  {item.label} ↗
                </a>
              ))}
            </div>
          ) : null}
        </Card>

        <Card className="shadow-sm lg:col-span-2">
          <h2 className="text-h4 font-bold text-ink">Prospect Metadata</h2>
          <dl className="mt-4 grid gap-4 sm:grid-cols-2 lg:grid-cols-1">
            <DetailItem label="Industry" value={lead.industry} />
            <DetailItem label="Acquisition Source" value={lead.source} />
            <DetailItem label="Discovered" value={formatWhen(lead.created_at)} />
            <DetailItem label="Last Activity" value={formatWhen(lead.updated_at)} />
          </dl>
          {lead.tags.length > 0 ? (
            <div className="mt-4 flex flex-wrap gap-1 border-t border-gray-100 pt-4">
              {lead.tags.map((tag) => (
                <Badge key={tag}>{tag}</Badge>
              ))}
            </div>
          ) : null}
        </Card>
      </div>

      {lead.description ? (
        <Card className="shadow-sm">
          <h2 className="text-h4 font-bold text-ink">Business Description</h2>
          <p className="mt-2 whitespace-pre-wrap text-body text-gray-700 leading-relaxed">{lead.description}</p>
        </Card>
      ) : null}
      {lead.notes ? (
        <Card className="shadow-sm">
          <h2 className="text-h4 font-bold text-ink">Internal Notes</h2>
          <p className="mt-2 whitespace-pre-wrap text-body text-gray-700 leading-relaxed">{lead.notes}</p>
        </Card>
      ) : null}
    </div>
  );
}

function ActivityList({ lead }: { lead: LeadDetail }) {
  if (lead.activities.length === 0) {
    return (
      <EmptyState title="No activity yet" description="Events and interactions for this lead will collect here." />
    );
  }

  return (
    <ol>
      {lead.activities.map((activity, index) => (
        <li key={activity.id} className="relative flex gap-4 pb-4 last:pb-0">
          {index < lead.activities.length - 1 ? (
            <span className="absolute top-8 bottom-0 left-4 w-px bg-gray-200" aria-hidden="true" />
          ) : null}
          <span className="relative z-10 flex size-8 shrink-0 items-center justify-center rounded-full border border-gray-200 bg-white text-gray-600">
            <ActivityIcon type={activity.type} />
          </span>
          <article className="min-w-0 flex-1 rounded-card border border-gray-200 bg-white px-3 py-3 shadow-sm sm:px-4">
            <div className="flex flex-col gap-1 sm:flex-row sm:flex-wrap sm:items-baseline sm:justify-between sm:gap-x-3">
              <h3 className="font-semibold text-ink">{activity.title}</h3>
              <time className="text-caption text-gray-500" dateTime={activity.created_at}>
                {formatWhen(activity.created_at)}
              </time>
            </div>
            <p className="mt-1 text-caption font-medium text-gray-500">
              {activityLabel(activity.type)}
            </p>
            {activity.description ? (
              <p className="mt-2 text-body text-gray-700">{activity.description}</p>
            ) : null}
            <ActivityDetails details={activity.details} />
          </article>
        </li>
      ))}
    </ol>
  );
}

function ActivityDetails({ details }: { details: Activity["details"] }) {
  const lines = detailLines(details);
  if (lines.length === 0) {
    return null;
  }

  return (
    <dl className="mt-3 grid gap-2 rounded-control bg-gray-50 px-3 py-2 sm:grid-cols-2">
      {lines.map((line) => (
        <div key={line.label}>
          <dt className="text-caption text-gray-500">{line.label}</dt>
          <dd className="text-small text-ink">{line.value}</dd>
        </div>
      ))}
    </dl>
  );
}

function SummaryCard({
  label,
  value,
  detail,
  emphasis = false,
}: {
  label: string;
  value: string;
  detail?: string | null;
  emphasis?: boolean;
}) {
  return (
    <Card className={cn("shadow-sm p-4", emphasis && "border-amber-200 bg-amber-50/70")}>
      <p className="text-caption font-semibold text-gray-500">{label}</p>
      <p className="mt-1.5 text-h4 font-bold break-words text-ink">{value}</p>
      {detail ? <p className="mt-1 text-caption text-gray-500 truncate">{detail}</p> : null}
    </Card>
  );
}

function Fact({ icon, label, children }: { icon: ReactNode; label: string; children: ReactNode }) {
  return (
    <div className="flex gap-3 border-b border-gray-100 py-3 last:border-b-0">
      <span className="mt-0.5 flex size-8 shrink-0 items-center justify-center rounded-full bg-gray-50 text-gray-500">
        {icon}
      </span>
      <div className="min-w-0">
        <dt className="text-caption font-medium text-gray-500">{label}</dt>
        <dd className="mt-0.5 text-body text-ink">{children}</dd>
      </div>
    </div>
  );
}

function DetailItem({ label, value }: { label: string; value: string | null }) {
  return (
    <div>
      <dt className="text-caption font-semibold text-gray-500">{label}</dt>
      <dd className="mt-1 text-body text-ink">{value || "—"}</dd>
    </div>
  );
}

function ActivityIcon({ type }: { type: string }) {
  const className = "size-4";
  if (type.startsWith("outreach")) {
    return <Mail className={className} aria-hidden="true" />;
  }
  if (type.startsWith("audit")) {
    return <Globe className={className} aria-hidden="true" />;
  }
  if (type.startsWith("research")) {
    return <Sparkles className={className} aria-hidden="true" />;
  }
  if (type.startsWith("mockup")) {
    return <Images className={className} aria-hidden="true" />;
  }
  if (type.startsWith("followup")) {
    return <CalendarClock className={className} aria-hidden="true" />;
  }
  if (type.startsWith("tag")) {
    return <Tag className={className} aria-hidden="true" />;
  }
  if (type === "status_changed" || type === "lead_updated") {
    return <RefreshCw className={className} aria-hidden="true" />;
  }
  return <CircleDot className={className} aria-hidden="true" />;
}

function activityLabel(type: string): string {
  return type
    .split("_")
    .map((part) => part.charAt(0).toUpperCase() + part.slice(1))
    .join(" ");
}

function detailLines(details: Activity["details"]): { label: string; value: string }[] {
  if (!details) {
    return [];
  }
  return Object.entries(details)
    .flatMap(([key, value]) => {
      if (typeof value !== "string" && typeof value !== "number" && typeof value !== "boolean") {
        return [];
      }
      return [
        {
          label: key
            .split("_")
            .map((part) => part.charAt(0).toUpperCase() + part.slice(1))
            .join(" "),
          value: String(value),
        },
      ];
    })
    .slice(0, 4);
}

function linkItem(label: string, href: string | null): { label: string; href: string } | null {
  if (!href) {
    return null;
  }
  return { label, href };
}

function isPast(value: string | null): boolean {
  if (!value) {
    return false;
  }
  const date = new Date(value);
  return !Number.isNaN(date.getTime()) && date.getTime() < Date.now();
}

import {
  ArrowLeft,
  CalendarClock,
  CircleDot,
  Globe,
  Mail,
  MapPin,
  Phone,
  RefreshCw,
  Tag,
} from "lucide-react";
import { useState, type ReactNode } from "react";
import { useNavigate, useParams } from "react-router-dom";

import { EmptyState } from "../components/feedback/EmptyState";
import { useToast } from "../components/feedback/useToast";
import { PageHeader } from "../components/layout/PageHeader";
import { Badge, StatusBadge } from "../components/ui/Badge";
import { Button } from "../components/ui/Button";
import { Card } from "../components/ui/Card";
import { Modal } from "../components/ui/Modal";
import { Skeleton } from "../components/ui/Skeleton";
import { Tabs } from "../components/ui/Tabs";
import { MockupGallery } from "../features/mockups/MockupGallery";
import { ConversationPanel } from "../features/gmail/ConversationPanel";
import { GmailComposer } from "../features/gmail/GmailComposer";
import { MessageList } from "../features/outreach/MessageList";
import { OutreachComposer } from "../features/outreach/OutreachComposer";
import { AuditPanel } from "../features/audits/AuditPanel";
import { useDeleteLead, useLead } from "../hooks/useLeads";
import { apiErrorCode, apiErrorMessage } from "../lib/apiError";
import { cn, focusRing } from "../lib/cn";
import { formatWhen } from "../lib/format";
import type { Activity, LeadDetail } from "../types/lead";

function BackToLeads() {
  const navigate = useNavigate();

  return (
    <Button
      variant="ghost"
      className="-ml-3 mb-4"
      onClick={() => {
        navigate("/leads");
      }}
    >
      <ArrowLeft className="size-4" aria-hidden="true" />
      Back to leads
    </Button>
  );
}

export function LeadDetailPage() {
  const { leadId = "" } = useParams();
  const navigate = useNavigate();
  const lead = useLead(leadId);

  if (lead.isPending) {
    return (
      <div aria-busy="true">
        <BackToLeads />
        <div className="space-y-3">
          <Skeleton className="h-10 w-64" />
          <Skeleton className="h-40 w-full" />
        </div>
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
  const { notify } = useToast();
  const removeLead = useDeleteLead();
  const [confirming, setConfirming] = useState(false);
  const [outreachFocus, setOutreachFocus] = useState<string | null>(null);

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

  return (
    <>
      <BackToLeads />
      <PageHeader
        title={lead.business_name}
        description={
          [lead.industry, lead.city, lead.country].filter(Boolean).join(" · ") || undefined
        }
        actions={
          <>
            {lead.email_unread ? <Badge tone="orange">Unread reply</Badge> : null}
            {lead.do_not_contact ? <Badge tone="red">Do not contact</Badge> : null}
            <StatusBadge status={lead.lead_status} />
            <Button
              variant="secondary"
              onClick={() => {
                navigate(`/leads/${lead.id}/edit`);
              }}
            >
              Edit
            </Button>
            <Button
              variant="secondary"
              onClick={() => {
                setConfirming(true);
              }}
            >
              Delete
            </Button>
          </>
        }
      />
      <Tabs
        label="Lead sections"
        tabs={[
          { id: "overview", label: "Overview", content: <Overview lead={lead} /> },
          {
            id: "audit",
            label: "Audit",
            content: <AuditPanel leadId={lead.id} websiteUrl={lead.website_url} />,
          },
          {
            id: "mockups",
            label: "Mockups",
            content: <MockupGallery leadId={lead.id} />,
          },
          {
            id: "outreach",
            label: "Outreach",
            content: (
              <div className="space-y-6">
                <div className="grid items-start gap-6 xl:grid-cols-2">
                  <OutreachComposer
                    leadId={lead.id}
                    email={lead.email}
                    hasWebsite={Boolean(lead.website_url) && lead.website_status !== "missing"}
                    onCreated={setOutreachFocus}
                  />
                  <section>
                    <h2 className="text-h4 font-semibold text-ink">Messages</h2>
                    <p className="mt-1 text-small text-gray-600">
                      Review a draft, send it with Gmail or your mail app, then track replies here.
                    </p>
                    <div className="mt-4">
                      <MessageList leadId={lead.id} focusId={outreachFocus} expandFirstDraft />
                    </div>
                  </section>
                </div>
                <div className="grid items-start gap-6 xl:grid-cols-2">
                  <GmailComposer leadId={lead.id} defaultTo={lead.email} />
                  <ConversationPanel leadId={lead.id} />
                </div>
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
      <Modal
        open={confirming}
        title="Delete this lead?"
        description="Notes and activity for this lead will be removed."
        onClose={() => {
          setConfirming(false);
        }}
      >
        <div className="flex flex-wrap justify-end gap-2">
          <Button
            variant="secondary"
            onClick={() => {
              setConfirming(false);
            }}
          >
            Cancel
          </Button>
          <Button onClick={remove} isLoading={removeLead.isPending}>
            Delete lead
          </Button>
        </div>
      </Modal>
    </>
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

function Overview({ lead }: { lead: LeadDetail }) {
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
      <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-5">
        <Card className="shadow-sm">
          <p className="text-caption font-semibold text-gray-500">Lead score</p>
          <p className="mt-2 text-h2 font-bold text-ink tabular-nums">{lead.lead_score ?? "—"}</p>
          <div className="mt-3 h-1.5 overflow-hidden rounded-full bg-gray-100">
            <div
              className={cn("h-full rounded-full", scoreColor(lead.lead_score))}
              style={{ width: `${scoreWidth(lead.lead_score)}%` }}
            />
          </div>
          <p className="mt-2 text-caption text-gray-500">
            Higher means a stronger reason to pitch.
          </p>
        </Card>
        <SummaryCard
          label="Website"
          value={websiteStatusLabels[lead.website_status ?? ""] ?? lead.website_status ?? "Unknown"}
          detail={
            lead.website_quality_score === null ? null : `Quality ${lead.website_quality_score}`
          }
        />
        <SummaryCard
          label="Last contacted"
          value={lead.last_contacted_at ? formatWhen(lead.last_contacted_at) : "Not yet"}
        />
        <SummaryCard
          label="Last reply"
          value={lead.last_replied_at ? formatWhen(lead.last_replied_at) : "None yet"}
          emphasis={lead.email_unread}
        />
        <SummaryCard
          label="Next follow-up"
          value={lead.next_followup_at ? formatWhen(lead.next_followup_at) : "None set"}
          emphasis={followUpOverdue}
        />
      </div>

      <div className="grid gap-4 lg:grid-cols-5">
        <Card className="shadow-sm lg:col-span-3">
          <h2 className="text-h4 font-semibold text-ink">How to reach them</h2>
          <dl className="mt-2">
            <Fact icon={<Mail className="size-4" aria-hidden="true" />} label="Email">
              {lead.email ? (
                <a href={`mailto:${lead.email}`} className={cn("text-primary-700", focusRing)}>
                  {lead.email}
                </a>
              ) : (
                "—"
              )}
            </Fact>
            <Fact icon={<Phone className="size-4" aria-hidden="true" />} label="Phone">
              {lead.phone ? (
                <a href={`tel:${lead.phone}`} className={cn("text-primary-700", focusRing)}>
                  {lead.phone}
                </a>
              ) : (
                "—"
              )}
            </Fact>
            <Fact icon={<Globe className="size-4" aria-hidden="true" />} label="Website">
              {lead.website_url ? (
                <a
                  href={lead.website_url}
                  target="_blank"
                  rel="noreferrer"
                  className={cn("break-all text-primary-700", focusRing)}
                >
                  {lead.website_url}
                </a>
              ) : (
                "—"
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
                  {item.label}
                </a>
              ))}
            </div>
          ) : null}
        </Card>

        <Card className="shadow-sm lg:col-span-2">
          <h2 className="text-h4 font-semibold text-ink">About this lead</h2>
          <dl className="mt-4 grid gap-4 sm:grid-cols-2 lg:grid-cols-1">
            <DetailItem label="Industry" value={lead.industry} />
            <DetailItem label="Source" value={lead.source} />
            <DetailItem label="Added" value={formatWhen(lead.created_at)} />
            <DetailItem label="Updated" value={formatWhen(lead.updated_at)} />
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
          <h2 className="text-h4 font-semibold text-ink">Description</h2>
          <p className="mt-3 whitespace-pre-wrap text-body text-gray-700">{lead.description}</p>
        </Card>
      ) : null}
      {lead.notes ? (
        <Card className="shadow-sm">
          <h2 className="text-h4 font-semibold text-ink">Notes</h2>
          <p className="mt-3 whitespace-pre-wrap text-body text-gray-700">{lead.notes}</p>
        </Card>
      ) : null}
    </div>
  );
}

function ActivityList({ lead }: { lead: LeadDetail }) {
  if (lead.activities.length === 0) {
    return (
      <EmptyState title="No activity yet" description="Changes to this lead will collect here." />
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
          <article className="min-w-0 flex-1 rounded-card border border-gray-200 bg-white px-4 py-3 shadow-sm">
            <div className="flex flex-wrap items-baseline justify-between gap-x-3 gap-y-1">
              <h3 className="font-medium text-ink">{activity.title}</h3>
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
    <Card className={cn("shadow-sm", emphasis && "border-amber-200 bg-amber-50")}>
      <p className="text-caption font-semibold text-gray-500">{label}</p>
      <p className="mt-2 text-h4 font-semibold text-ink">{value}</p>
      {detail ? <p className="mt-1 text-caption text-gray-500">{detail}</p> : null}
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

function scoreWidth(score: number | null): number {
  if (score === null) {
    return 0;
  }
  return Math.max(0, Math.min(100, score));
}

function scoreColor(score: number | null): string {
  if (score === null) {
    return "bg-gray-200";
  }
  if (score >= 70) {
    return "bg-emerald-500";
  }
  if (score >= 40) {
    return "bg-amber-400";
  }
  return "bg-red-400";
}

function isPast(value: string | null): boolean {
  if (!value) {
    return false;
  }
  const date = new Date(value);
  return !Number.isNaN(date.getTime()) && date.getTime() < Date.now();
}

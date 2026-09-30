import { ArrowLeft } from "lucide-react";
import { useState } from "react";
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
import { MessageList } from "../features/outreach/MessageList";
import { OutreachComposer } from "../features/outreach/OutreachComposer";
import { AuditPanel } from "../features/audits/AuditPanel";
import { useDeleteLead, useLead } from "../hooks/useLeads";
import { apiErrorCode, apiErrorMessage } from "../lib/apiError";
import { formatWhen } from "../lib/format";
import type { LeadDetail } from "../types/lead";

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
        description={[lead.city, lead.country].filter(Boolean).join(", ") || undefined}
        actions={
          <>
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
            content: (
              <div className="mt-6">
                <MockupGallery leadId={lead.id} />
              </div>
            ),
          },
          {
            id: "outreach",
            label: "Outreach",
            content: (
              <div className="mt-6 space-y-6">
                <OutreachComposer
                  leadId={lead.id}
                  email={lead.email}
                  onCreated={setOutreachFocus}
                />
                <MessageList leadId={lead.id} focusId={outreachFocus} expandFirstDraft />
              </div>
            ),
          },
          { id: "activity", label: "Activity", content: <ActivityList lead={lead} /> },
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

function Overview({ lead }: { lead: LeadDetail }) {
  return (
    <div className="mt-6 space-y-6">
      <Card>
        <dl className="grid gap-4 sm:grid-cols-2">
          <DetailItem label="Industry" value={lead.industry} />
          <DetailItem label="Source" value={lead.source} />
          <DetailItem label="Email" value={lead.email} />
          <DetailItem label="Phone" value={lead.phone} />
          <div>
            <dt className="text-caption font-semibold text-gray-500">Website</dt>
            <dd className="mt-1 text-body text-ink">
              {lead.website_url ? (
                <a
                  href={lead.website_url}
                  className="text-primary-700"
                  target="_blank"
                  rel="noreferrer"
                >
                  {lead.website_url}
                </a>
              ) : (
                "—"
              )}
            </dd>
          </div>
          <DetailItem label="Website status" value={lead.website_status} />
          <DetailItem
            label="Lead score"
            value={lead.lead_score === null ? null : String(lead.lead_score)}
          />
          <DetailItem label="Added" value={formatWhen(lead.created_at)} />
        </dl>
        {lead.tags.length > 0 ? (
          <div className="mt-4 flex flex-wrap gap-1">
            {lead.tags.map((tag) => (
              <Badge key={tag}>{tag}</Badge>
            ))}
          </div>
        ) : null}
        {lead.notes ? (
          <p className="mt-4 whitespace-pre-wrap text-body text-gray-700">{lead.notes}</p>
        ) : null}
      </Card>
    </div>
  );
}

function ActivityList({ lead }: { lead: LeadDetail }) {
  if (lead.activities.length === 0) {
    return (
      <div className="mt-6">
        <EmptyState title="No activity yet" description="Changes to this lead will collect here." />
      </div>
    );
  }

  return (
    <ol className="mt-6 space-y-4">
      {lead.activities.map((activity) => (
        <li key={activity.id} className="border-b border-gray-200 pb-4">
          <p className="font-medium text-ink">{activity.title}</p>
          {activity.description ? (
            <p className="mt-1 text-body text-gray-600">{activity.description}</p>
          ) : null}
          <p className="mt-1 text-small text-gray-500">{formatWhen(activity.created_at)}</p>
        </li>
      ))}
    </ol>
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

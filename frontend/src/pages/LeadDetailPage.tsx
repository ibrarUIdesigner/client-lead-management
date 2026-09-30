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
import { ContactForm } from "../features/leads/ContactForm";
import { MockupGallery } from "../features/mockups/MockupGallery";
import { MessageList } from "../features/outreach/MessageList";
import { AuditPanel } from "../features/audits/AuditPanel";
import { useDeleteContact, useUpdateContact } from "../hooks/useContacts";
import { useDeleteLead, useLead } from "../hooks/useLeads";
import { apiErrorCode, apiErrorMessage } from "../lib/apiError";
import { formatWhen } from "../lib/format";
import type { LeadDetail } from "../types/lead";

export function LeadDetailPage() {
  const { leadId = "" } = useParams();
  const navigate = useNavigate();
  const lead = useLead(leadId);

  if (lead.isPending) {
    return (
      <div className="space-y-3" aria-busy="true">
        <Skeleton className="h-10 w-64" />
        <Skeleton className="h-40 w-full" />
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
    );
  }

  return <LeadDetailView lead={lead.data} />;
}

function LeadDetailView({ lead }: { lead: LeadDetail }) {
  const navigate = useNavigate();
  const { notify } = useToast();
  const removeLead = useDeleteLead();
  const [confirming, setConfirming] = useState(false);

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
              <div className="mt-6">
                <MessageList leadId={lead.id} />
              </div>
            ),
          },
          { id: "activity", label: "Activity", content: <ActivityList lead={lead} /> },
        ]}
      />
      <Modal
        open={confirming}
        title="Delete this lead?"
        description="Contacts, notes, and activity for this lead will be removed."
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
      <Card>
        <h2 className="text-h4 font-semibold text-ink">Contacts</h2>
        <div className="mt-4">
          <ContactList lead={lead} />
        </div>
        <div className="mt-6 border-t border-gray-200 pt-6">
          <ContactForm leadId={lead.id} />
        </div>
      </Card>
    </div>
  );
}

function ContactList({ lead }: { lead: LeadDetail }) {
  const { notify } = useToast();
  const updateContact = useUpdateContact(lead.id);
  const deleteContact = useDeleteContact(lead.id);
  const [pendingId, setPendingId] = useState<string | null>(null);

  if (lead.contacts.length === 0) {
    return <p className="text-body text-gray-600">No contacts yet.</p>;
  }

  return (
    <ul className="divide-y divide-gray-200">
      {lead.contacts.map((contact) => (
        <li
          key={contact.id}
          className="flex flex-col gap-3 py-4 sm:flex-row sm:items-start sm:justify-between"
        >
          <div>
            <p className="font-medium text-ink">
              {contact.name}
              {contact.is_primary ? (
                <span className="ml-2">
                  <Badge tone="indigo">Primary</Badge>
                </span>
              ) : null}
            </p>
            <p className="text-small text-gray-600">
              {[contact.job_title, contact.email, contact.phone].filter(Boolean).join(" · ") || "—"}
            </p>
          </div>
          <div className="flex flex-wrap gap-2">
            {contact.is_primary ? null : (
              <Button
                variant="secondary"
                disabled={updateContact.isPending}
                onClick={() => {
                  updateContact.mutate(
                    { contactId: contact.id, payload: { is_primary: true } },
                    {
                      onError: (error) => {
                        notify(apiErrorMessage(error, "Could not update the contact."), "danger");
                      },
                    },
                  );
                }}
              >
                Make primary
              </Button>
            )}
            {pendingId === contact.id ? (
              <Button
                variant="secondary"
                isLoading={deleteContact.isPending}
                onClick={() => {
                  deleteContact.mutate(contact.id, {
                    onSuccess: () => {
                      notify("Contact removed.", "success");
                      setPendingId(null);
                    },
                    onError: (error) => {
                      notify(apiErrorMessage(error, "Could not remove the contact."), "danger");
                    },
                  });
                }}
              >
                Confirm remove
              </Button>
            ) : (
              <Button
                variant="ghost"
                onClick={() => {
                  setPendingId(contact.id);
                }}
              >
                Remove
              </Button>
            )}
          </div>
        </li>
      ))}
    </ul>
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

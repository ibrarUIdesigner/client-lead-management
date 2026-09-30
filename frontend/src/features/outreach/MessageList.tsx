import { useState } from "react";
import { Link } from "react-router-dom";

import { EmptyState } from "../../components/feedback/EmptyState";
import { QueryGate } from "../../components/feedback/QueryGate";
import { useToast } from "../../components/feedback/useToast";
import { Badge, StatusBadge } from "../../components/ui/Badge";
import { Button } from "../../components/ui/Button";
import { Card } from "../../components/ui/Card";
import { Input } from "../../components/ui/Input";
import { Textarea } from "../../components/ui/Textarea";
import { FollowUpSchedule } from "../followups/FollowUpSchedule";
import { useMarkContacted, useMarkReplied, useUpdateOutreach } from "../../hooks/useOutreach";
import { useOutreachMessages } from "../../hooks/useWorkspace";
import { apiErrorMessage } from "../../lib/apiError";
import { cn, focusRing } from "../../lib/cn";
import { formatWhen } from "../../lib/format";
import type { OutreachMessageItem } from "../../types/workspace";
import { copyOutreach, mailtoUrl } from "./mail";

type MessageListProps = {
  leadId?: string;
  focusId?: string | null;
  expandFirstDraft?: boolean;
};

export function MessageList({ leadId, focusId, expandFirstDraft = false }: MessageListProps) {
  const messages = useOutreachMessages(leadId);
  const firstDraftId = expandFirstDraft
    ? messages.data?.find((item) => isDraft(item.status))?.id
    : undefined;
  const openId = focusId || firstDraftId;

  return (
    <QueryGate
      pending={messages.isPending}
      error={messages.error}
      onRetry={() => {
        void messages.refetch();
      }}
      fallback="Outreach could not be loaded."
    >
      {messages.data && messages.data.length === 0 ? (
        <EmptyState
          title="No outreach yet"
          description={
            leadId
              ? "The findings above become the email. Write the draft, send it from your email app, then mark it here."
              : "Open a lead to write an email. Drafts you can send will show up here."
          }
        />
      ) : null}
      {messages.data && messages.data.length > 0 ? (
        <div className="space-y-4">
          {messages.data.map((item) => (
            <MessageCard
              key={item.id}
              item={item}
              startEditing={item.id === openId}
              onLeadPage={Boolean(leadId)}
            />
          ))}
        </div>
      ) : null}
    </QueryGate>
  );
}

function MessageCard({
  item,
  startEditing,
  onLeadPage,
}: {
  item: OutreachMessageItem;
  startEditing: boolean;
  onLeadPage: boolean;
}) {
  const { notify } = useToast();
  const updateOutreach = useUpdateOutreach();
  const markContacted = useMarkContacted();
  const markReplied = useMarkReplied();
  const [openedManually, setOpenedManually] = useState(false);
  const [subject, setSubject] = useState(item.subject ?? "");
  const [body, setBody] = useState(item.message ?? "");
  const [busy, setBusy] = useState(false);
  const when = item.replied_at ?? item.opened_at ?? item.sent_at ?? item.created_at;
  const draft = isDraft(item.status);
  const editing = draft && (startEditing || openedManually);
  const dirty = subject !== (item.subject ?? "") || body !== (item.message ?? "");
  const ready = subject.trim().length > 0 && body.trim().length > 0;
  const pending =
    busy || updateOutreach.isPending || markContacted.isPending || markReplied.isPending;

  const persist = async () => {
    if (!dirty) {
      return item;
    }
    return updateOutreach.mutateAsync({
      messageId: item.id,
      payload: { subject, message: body },
    });
  };

  const copy = async () => {
    try {
      await copyOutreach(subject, body);
      notify("Copied.", "success");
    } catch {
      notify("Could not copy the email.", "danger");
    }
  };

  const openEmail = async () => {
    if (!item.recipient_email || !ready) {
      return;
    }
    setBusy(true);
    try {
      const saved = await persist();
      setSubject(saved.subject ?? "");
      setBody(saved.message ?? "");
      window.location.href = mailtoUrl(
        item.recipient_email,
        saved.subject ?? "",
        saved.message ?? "",
      );
    } catch (error) {
      notify(apiErrorMessage(error, "Could not save the draft."), "danger");
    } finally {
      setBusy(false);
    }
  };

  const recordSent = async () => {
    setBusy(true);
    try {
      const saved = await persist();
      setSubject(saved.subject ?? "");
      setBody(saved.message ?? "");
      await markContacted.mutateAsync(item.id);
      notify("Marked as contacted.", "success");
      setOpenedManually(false);
    } catch (error) {
      notify(apiErrorMessage(error, "Could not record the email."), "danger");
    } finally {
      setBusy(false);
    }
  };

  const recordReply = async () => {
    setBusy(true);
    try {
      if (draft) {
        const saved = await persist();
        setSubject(saved.subject ?? "");
        setBody(saved.message ?? "");
      }
      await markReplied.mutateAsync(item.id);
      notify("Reply recorded.", "success");
      setOpenedManually(false);
    } catch (error) {
      notify(apiErrorMessage(error, "Could not record the reply."), "danger");
    } finally {
      setBusy(false);
    }
  };

  return (
    <Card>
      <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
        <div>
          {onLeadPage ? null : (
            <Link
              to={`/leads/${item.lead_id}`}
              className={cn("font-semibold text-ink hover:text-primary-700", focusRing)}
            >
              {item.business_name}
            </Link>
          )}
          {editing ? (
            <p className="font-semibold text-ink">Email draft</p>
          ) : (
            <p className={cn("text-body text-ink", onLeadPage ? "font-semibold" : "mt-1")}>
              {item.subject || "No subject"}
            </p>
          )}
          <p className="mt-1 text-small text-gray-600">
            {[item.recipient_email, item.channel, formatWhen(when)].filter(Boolean).join(" · ")}
          </p>
        </div>
        <div className="flex flex-wrap gap-2">
          {item.channel ? <Badge>{item.channel}</Badge> : null}
          <StatusBadge status={item.status} />
        </div>
      </div>
      {editing && draft ? (
        <div className="mt-4 space-y-4">
          <Input
            label="Subject"
            value={subject}
            onChange={(event) => {
              setSubject(event.target.value);
            }}
          />
          <Textarea
            label="Message"
            value={body}
            onChange={(event) => {
              setBody(event.target.value);
            }}
          />
        </div>
      ) : item.message ? (
        <p className="mt-4 whitespace-pre-wrap text-body text-gray-700">{item.message}</p>
      ) : null}
      <div className="mt-4">
        <p className="text-caption font-semibold text-gray-500">
          {draft ? "3. Send it yourself, then record it" : nextStep(item.status)}
        </p>
        <div className="mt-2 flex flex-wrap gap-2">
          {draft && !editing ? (
            <Button
              variant="secondary"
              onClick={() => {
                setOpenedManually(true);
              }}
            >
              Edit
            </Button>
          ) : null}
          {draft && editing && dirty ? (
            <Button
              variant="secondary"
              isLoading={updateOutreach.isPending && !busy}
              disabled={pending}
              onClick={() => {
                setBusy(true);
                persist()
                  .then((saved) => {
                    setSubject(saved.subject ?? "");
                    setBody(saved.message ?? "");
                    notify("Draft saved.", "success");
                  })
                  .catch((error: unknown) => {
                    notify(apiErrorMessage(error, "Could not save the draft."), "danger");
                  })
                  .finally(() => {
                    setBusy(false);
                  });
              }}
            >
              Save
            </Button>
          ) : null}
          <Button variant="secondary" disabled={!ready || pending} onClick={() => void copy()}>
            Copy
          </Button>
          <Button
            variant="secondary"
            disabled={!ready || !item.recipient_email || pending}
            onClick={() => void openEmail()}
          >
            Open in email
          </Button>
          {draft ? (
            <Button disabled={!ready || pending} onClick={() => void recordSent()}>
              I sent this
            </Button>
          ) : null}
          {item.status !== "REPLIED" && item.status !== "CANCELLED" ? (
            <Button
              variant="secondary"
              disabled={!ready || pending}
              onClick={() => void recordReply()}
            >
              They replied
            </Button>
          ) : null}
        </div>
      </div>
      {draft ? (
        <p className="mt-3 text-small text-gray-600">
          Open in email uses your mail app. Nothing is sent until you send it there.
          {item.recipient_email ? "" : " Add an email on the lead to use that button."}
        </p>
      ) : null}
      {item.status === "SENT" || item.status === "OPENED" || item.status === "REPLIED" ? (
        <FollowUpSchedule leadId={item.lead_id} outreachId={item.id} />
      ) : null}
    </Card>
  );
}

function isDraft(status: string): boolean {
  return status === "DRAFT" || status === "READY";
}

function nextStep(status: string): string {
  if (status === "REPLIED") {
    return "They replied. Move the lead on the pipeline when you are ready.";
  }
  if (status === "CANCELLED") {
    return "This note was cancelled.";
  }
  return "Waiting for a reply. Set a follow-up if you want a reminder.";
}

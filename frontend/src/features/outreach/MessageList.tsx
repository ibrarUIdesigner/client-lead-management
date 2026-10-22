import { useState } from "react";
import { Link } from "react-router-dom";
import { CheckCircle2, Sparkles } from "lucide-react";

import { EmptyState } from "../../components/feedback/EmptyState";
import { QueryGate } from "../../components/feedback/QueryGate";
import { useToast } from "../../components/feedback/useToast";
import { Badge, StatusBadge } from "../../components/ui/Badge";
import { Button } from "../../components/ui/Button";
import { Card } from "../../components/ui/Card";
import { Input } from "../../components/ui/Input";
import { Textarea } from "../../components/ui/Textarea";
import { FollowUpSchedule } from "../followups/FollowUpSchedule";
import { useGmailStatus, useSendLeadEmail } from "../../hooks/useGmail";
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
  statuses?: string[];
  onSelect?: (item: OutreachMessageItem) => void;
};

export function MessageList({
  leadId,
  focusId,
  expandFirstDraft = false,
  statuses,
  onSelect,
}: MessageListProps) {
  const messages = useOutreachMessages(leadId);
  const visible = (messages.data ?? []).filter(
    (item) => !statuses || statuses.includes(item.status),
  );
  const firstDraftId = expandFirstDraft
    ? visible.find((item) => isDraft(item.status))?.id
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
      {messages.data && visible.length === 0 ? (
        <EmptyState
          compact={Boolean(leadId) || Boolean(statuses)}
          title={messages.data.length === 0 ? "No outreach yet" : "Nothing in this view"}
          description={
            messages.data.length === 0
              ? leadId
                ? "Write the draft above. It shows up here, ready to review and send."
                : "Open a lead, write a draft from its audit, then send it from here."
              : "Try another filter. Drafts, sent notes, and replies are kept."
          }
        />
      ) : null}
      {visible.length > 0 ? (
        <div className="space-y-4">
          {visible.map((item) => (
            <MessageCard
              key={item.id}
              item={item}
              startEditing={item.id === openId}
              onLeadPage={Boolean(leadId)}
              onSelect={onSelect}
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
  onSelect,
}: {
  item: OutreachMessageItem;
  startEditing: boolean;
  onLeadPage: boolean;
  onSelect?: (item: OutreachMessageItem) => void;
}) {
  const { notify } = useToast();
  const updateOutreach = useUpdateOutreach();
  const markContacted = useMarkContacted();
  const markReplied = useMarkReplied();
  const gmail = useGmailStatus();
  const sendGmail = useSendLeadEmail(item.lead_id);
  const [openedManually, setOpenedManually] = useState(false);
  const [subject, setSubject] = useState(item.subject ?? "");
  const [body, setBody] = useState(item.message ?? "");
  const [busy, setBusy] = useState(false);
  const when = item.replied_at ?? item.opened_at ?? item.sent_at ?? item.created_at;
  const draft = isDraft(item.status);
  const editing = draft && (startEditing || openedManually);
  const dirty = subject !== (item.subject ?? "") || body !== (item.message ?? "");
  const ready = subject.trim().length > 0 && body.trim().length > 0;
  const gmailReady = Boolean(gmail.data?.connected && !gmail.data.needs_reauth);
  const pending =
    busy ||
    updateOutreach.isPending ||
    markContacted.isPending ||
    markReplied.isPending ||
    sendGmail.isPending;

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
      notify("Copied to clipboard.", "success");
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

  const sendWithGmail = async () => {
    if (!item.recipient_email || !ready || pending) {
      return;
    }
    setBusy(true);
    try {
      const saved = await persist();
      setSubject(saved.subject ?? "");
      setBody(saved.message ?? "");
      await sendGmail.mutateAsync({
        to: item.recipient_email,
        subject: saved.subject ?? subject,
        body: saved.message ?? body,
        outreach_message_id: item.id,
        idempotency_key: crypto.randomUUID(),
      });
      notify("Email sent via Gmail.", "success");
      setOpenedManually(false);
    } catch (error) {
      notify(apiErrorMessage(error, "Could not send via Gmail."), "danger");
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
    <Card className={cn(draft ? "border-primary-200 bg-white shadow-sm" : "")}>
      {draft ? (
        <div className="flex items-center justify-between pb-3 mb-3 border-b border-gray-100">
          <div className="flex items-center gap-2">
            <Sparkles className="size-4 text-primary-600" />
            <span className="text-caption font-bold uppercase tracking-wider text-primary-800">
              AI Generated Draft — Manual Review
            </span>
          </div>
          <span className="text-caption text-gray-400">
            Never sent automatically
          </span>
        </div>
      ) : null}

      <div
        className={cn(
          "flex flex-col gap-2 sm:flex-row sm:items-start sm:justify-between",
          onSelect && "cursor-pointer",
        )}
        onClick={() => {
          onSelect?.(item);
        }}
        onKeyDown={(event) => {
          if (!onSelect) {
            return;
          }
          if (event.key === "Enter" || event.key === " ") {
            event.preventDefault();
            onSelect(item);
          }
        }}
        role={onSelect ? "button" : undefined}
        tabIndex={onSelect ? 0 : undefined}
      >
        <div>
          {onLeadPage || onSelect ? null : (
            <Link
              to={`/leads/${item.lead_id}`}
              className={cn("font-semibold text-ink hover:text-primary-700", focusRing)}
            >
              {item.business_name}
            </Link>
          )}
          {onSelect ? <p className="font-semibold text-ink">{item.business_name}</p> : null}
          {editing ? (
            <p className="font-semibold text-ink">Review & Edit Draft</p>
          ) : (
            <p className={cn("text-body text-ink font-semibold", onLeadPage ? "" : "mt-1")}>
              {item.subject || "No subject"}
            </p>
          )}
          <p className="mt-1 text-small text-gray-600">
            To: {item.recipient_email || "No email"} · {formatWhen(when)}
          </p>
          {onSelect ? (
            <p className="mt-2 text-small font-semibold text-primary-700">Open conversation</p>
          ) : null}
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
            rows={10}
            value={body}
            onChange={(event) => {
              setBody(event.target.value);
            }}
          />
        </div>
      ) : item.message ? (
        <p
          className="mt-4 rounded-control border border-gray-100 bg-gray-50/80 px-4 py-3 whitespace-pre-wrap text-body text-gray-800 leading-relaxed font-normal"
          onClick={() => {
            onSelect?.(item);
          }}
        >
          {item.message}
        </p>
      ) : null}

      {/* Personalization Badges (Section 26) */}
      {draft ? (
        <div className="mt-3 flex flex-wrap items-center gap-2 border-t border-gray-100 pt-3 text-[11px] text-gray-500">
          <span className="font-semibold text-gray-600">Personalization used:</span>
          <span className="inline-flex items-center gap-1 rounded bg-emerald-50 px-2 py-0.5 font-medium text-emerald-800">
            <CheckCircle2 className="size-3 text-emerald-600" /> Website audit
          </span>
          <span className="inline-flex items-center gap-1 rounded bg-indigo-50 px-2 py-0.5 font-medium text-indigo-800">
            <CheckCircle2 className="size-3 text-indigo-600" /> Business research
          </span>
          <span className="inline-flex items-center gap-1 rounded bg-blue-50 px-2 py-0.5 font-medium text-blue-800">
            <CheckCircle2 className="size-3 text-blue-600" /> Opportunity analysis
          </span>
        </div>
      ) : null}

      <div
        className="mt-4"
        onClick={(event) => {
          event.stopPropagation();
        }}
        onKeyDown={(event) => {
          event.stopPropagation();
        }}
      >
        <p className="text-caption font-semibold text-gray-500">
          {draft ? "Actions: Review, edit, or dispatch" : nextStep(item.status)}
        </p>
        <div className="mt-2 flex flex-wrap items-center gap-2">
          {draft && !editing ? (
            <Button
              variant="secondary"
              className="h-8 px-3 text-small"
              onClick={() => {
                setOpenedManually(true);
              }}
            >
              Edit Draft
            </Button>
          ) : null}
          {draft && editing && dirty ? (
            <Button
              variant="secondary"
              className="h-8 px-3 text-small"
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
              Save Changes
            </Button>
          ) : null}
          <Button
            variant="secondary"
            className="h-8 px-3 text-small"
            disabled={!ready || pending}
            onClick={() => void copy()}
          >
            Copy
          </Button>
          <Button
            variant="secondary"
            className="h-8 px-3 text-small"
            disabled={!ready || !item.recipient_email || pending}
            onClick={() => void openEmail()}
          >
            Open in Email Client
          </Button>
          {draft && gmailReady ? (
            <Button
              variant="primary"
              className="h-8 px-3 text-small"
              disabled={!ready || !item.recipient_email || pending}
              onClick={() => void sendWithGmail()}
            >
              Send with Gmail
            </Button>
          ) : null}
          {draft ? (
            <Button
              variant="secondary"
              className="h-8 px-3 text-small"
              disabled={!ready || pending}
              onClick={() => void recordSent()}
            >
              Mark Sent
            </Button>
          ) : null}
          {item.status !== "REPLIED" && item.status !== "CANCELLED" ? (
            <Button
              variant="secondary"
              className="h-8 px-3 text-small"
              disabled={!ready || pending}
              onClick={() => void recordReply()}
            >
              Mark Replied
            </Button>
          ) : null}
        </div>
      </div>
      {draft ? (
        <p className="mt-3 text-caption text-gray-500">
          Open in Email Client uses your default mail client. Send with Gmail delivers directly through your connected Google Workspace account.
          {item.recipient_email ? "" : " Add an email on the lead to enable direct sending."}
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

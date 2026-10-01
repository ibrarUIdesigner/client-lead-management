import { useEffect, useMemo, useRef, useState } from "react";
import { useQueryClient } from "@tanstack/react-query";

import { EmptyState } from "../../components/feedback/EmptyState";
import { QueryGate } from "../../components/feedback/QueryGate";
import { useToast } from "../../components/feedback/useToast";
import { Badge } from "../../components/ui/Badge";
import { Button } from "../../components/ui/Button";
import { Card } from "../../components/ui/Card";
import { Textarea } from "../../components/ui/Textarea";
import {
  useGmailStatus,
  useLeadEmails,
  useLeadEmailSync,
  useMarkLeadEmailsRead,
  useReplyLeadEmail,
} from "../../hooks/useGmail";
import { apiErrorMessage } from "../../lib/apiError";
import { cn } from "../../lib/cn";
import { formatWhen } from "../../lib/format";
import type { LeadEmailItem } from "../../services/gmail";

type ConversationPanelProps = {
  leadId: string;
};

export function ConversationPanel({ leadId }: ConversationPanelProps) {
  const { notify } = useToast();
  const queryClient = useQueryClient();
  const gmail = useGmailStatus();
  const thread = useLeadEmails(leadId);
  const markRead = useMarkLeadEmailsRead(leadId);
  const reply = useReplyLeadEmail(leadId);
  const sync = useLeadEmailSync(leadId);
  const [replyToId, setReplyToId] = useState<string | null>(null);
  const [replyBody, setReplyBody] = useState("");
  const [sending, setSending] = useState(false);
  const lastSignature = useRef<string>("");
  const syncMutate = sync.mutate;

  const connected = Boolean(gmail.data?.connected && !gmail.data.needs_reauth);

  const summary = useMemo(() => {
    if (!thread.data) {
      return null;
    }
    return thread.data;
  }, [thread.data]);

  useEffect(() => {
    if (!connected) {
      return;
    }
    const run = () => {
      syncMutate(undefined, {
        onError: () => {
          // Background sync failures stay quiet; the next interval retries.
        },
      });
    };
    run();
    const timer = window.setInterval(run, 45_000);
    return () => {
      window.clearInterval(timer);
    };
  }, [connected, leadId, syncMutate]);

  useEffect(() => {
    if (!summary) {
      return;
    }
    const signature = [
      summary.items.length,
      summary.unread_count,
      summary.last_replied_at ?? "",
      summary.email_unread ? "1" : "0",
    ].join("|");
    if (signature === lastSignature.current) {
      return;
    }
    lastSignature.current = signature;
    void queryClient.invalidateQueries({ queryKey: ["leads", leadId] });
    void queryClient.invalidateQueries({ queryKey: ["outreach"] });
    void queryClient.invalidateQueries({ queryKey: ["followups"] });
  }, [leadId, queryClient, summary]);

  const submitReply = (emailId: string) => {
    if (!replyBody.trim() || sending) {
      return;
    }
    setSending(true);
    const idempotencyKey = crypto.randomUUID();
    reply.mutate(
      {
        emailId,
        payload: { body: replyBody.trim(), idempotency_key: idempotencyKey },
      },
      {
        onSuccess: () => {
          notify("Reply sent via Gmail.", "success");
          setReplyBody("");
          setReplyToId(null);
        },
        onError: (error) => {
          notify(apiErrorMessage(error, "Could not send the reply."), "danger");
        },
        onSettled: () => {
          setSending(false);
        },
      },
    );
  };

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <h2 className="text-h4 font-semibold text-ink">Conversation</h2>
          <p className="mt-1 text-small text-gray-600">
            Sent and received Gmail messages for this lead. Replies sync automatically.
          </p>
        </div>
        <div className="flex flex-wrap gap-2">
          {connected ? (
            <Button
              variant="secondary"
              isLoading={sync.isPending}
              onClick={() => {
                sync.mutate(undefined, {
                  onSuccess: (result) => {
                    notify(
                      result.matched > 0
                        ? `Synced ${result.matched} new reply${result.matched === 1 ? "" : "s"}.`
                        : "Mailbox checked. No new matched replies.",
                      "success",
                    );
                  },
                  onError: (error) => {
                    notify(apiErrorMessage(error, "Gmail sync failed."), "danger");
                  },
                });
              }}
            >
              Sync replies
            </Button>
          ) : null}
          {summary?.email_unread ? (
            <Button
              variant="secondary"
              isLoading={markRead.isPending}
              onClick={() => {
                markRead.mutate(undefined, {
                  onSuccess: () => {
                    notify("Marked as read.", "success");
                  },
                  onError: (error) => {
                    notify(apiErrorMessage(error, "Could not mark as read."), "danger");
                  },
                });
              }}
            >
              Mark read
            </Button>
          ) : null}
        </div>
      </div>

      {summary &&
      (summary.items.length > 0 ||
        summary.email_unread ||
        summary.do_not_contact ||
        summary.email_suppressed) ? (
        <div className="flex flex-wrap gap-2">
          <Badge tone={summary.email_unread ? "orange" : "gray"}>
            {summary.email_unread ? `Unread (${summary.unread_count})` : "No unread"}
          </Badge>
          <Badge>
            Last contact:{" "}
            {summary.last_contacted_at ? formatWhen(summary.last_contacted_at) : "—"}
          </Badge>
          <Badge>
            Last reply: {summary.last_replied_at ? formatWhen(summary.last_replied_at) : "—"}
          </Badge>
          <Badge>
            Next follow-up:{" "}
            {summary.next_followup_at ? formatWhen(summary.next_followup_at) : "—"}
          </Badge>
          {summary.do_not_contact ? <Badge tone="red">Do not contact</Badge> : null}
          {summary.email_suppressed ? <Badge tone="red">Email suppressed</Badge> : null}
        </div>
      ) : null}

      {!connected ? (
        <Card>
          <p className="text-body text-gray-600">
            Connect Gmail in Settings to send and sync replies here.
          </p>
        </Card>
      ) : null}

      <QueryGate
        pending={thread.isPending}
        error={thread.error}
        onRetry={() => {
          void thread.refetch();
        }}
        fallback="Conversation could not be loaded."
      >
        {summary && summary.items.length === 0 ? (
          <EmptyState
            compact
            title="No Gmail messages yet"
            description="Sent mail and replies show up here after Gmail is connected."
          />
        ) : null}
        {summary && summary.items.length > 0 ? (
          <div className="space-y-3">
            {summary.items.map((item) => (
              <MessageBubble
                key={item.id}
                item={item}
                connected={connected}
                replying={replyToId === item.id}
                replyBody={replyBody}
                sending={sending || reply.isPending}
                onReply={() => {
                  setReplyToId(item.id);
                  setReplyBody("");
                }}
                onCancelReply={() => {
                  setReplyToId(null);
                  setReplyBody("");
                }}
                onChangeReply={setReplyBody}
                onSendReply={() => {
                  submitReply(item.id);
                }}
              />
            ))}
          </div>
        ) : null}
      </QueryGate>
    </div>
  );
}

function MessageBubble({
  item,
  connected,
  replying,
  replyBody,
  sending,
  onReply,
  onCancelReply,
  onChangeReply,
  onSendReply,
}: {
  item: LeadEmailItem;
  connected: boolean;
  replying: boolean;
  replyBody: string;
  sending: boolean;
  onReply: () => void;
  onCancelReply: () => void;
  onChangeReply: (value: string) => void;
  onSendReply: () => void;
}) {
  const outbound = item.direction === "OUTBOUND";
  return (
    <Card className={cn(item.is_unread ? "border-amber-200 bg-amber-50/40" : undefined)}>
      <div className="flex flex-wrap items-start justify-between gap-2">
        <div>
          <p className="font-semibold text-ink">{item.subject || "No subject"}</p>
          <p className="mt-1 text-small text-gray-600">
            {[
              outbound ? `To ${item.recipient_email ?? "—"}` : `From ${item.sender_email ?? "—"}`,
              formatWhen(item.occurred_at),
              classificationLabel(item.classification),
            ]
              .filter(Boolean)
              .join(" · ")}
          </p>
        </div>
        <div className="flex flex-wrap gap-2">
          <Badge tone={outbound ? "blue" : "green"}>{outbound ? "Sent" : "Received"}</Badge>
          {item.is_unread ? <Badge tone="orange">Unread</Badge> : null}
          {item.needs_review ? <Badge tone="orange">Needs review</Badge> : null}
        </div>
      </div>
      {item.body_html ? (
        <div
          className="prose prose-sm mt-4 max-w-none text-gray-700"
          dangerouslySetInnerHTML={{ __html: item.body_html }}
        />
      ) : item.body_text ? (
        <p className="mt-4 whitespace-pre-wrap text-body text-gray-700">{item.body_text}</p>
      ) : null}
      {connected && !outbound ? (
        <div className="mt-4">
          {!replying ? (
            <Button variant="secondary" onClick={onReply}>
              Reply
            </Button>
          ) : (
            <div className="space-y-3">
              <Textarea
                label="Reply"
                value={replyBody}
                onChange={(event) => {
                  onChangeReply(event.target.value);
                }}
              />
              <div className="flex flex-wrap gap-2">
                <Button
                  disabled={!replyBody.trim() || sending}
                  isLoading={sending}
                  onClick={onSendReply}
                >
                  Send reply
                </Button>
                <Button variant="ghost" disabled={sending} onClick={onCancelReply}>
                  Cancel
                </Button>
              </div>
            </div>
          )}
        </div>
      ) : null}
    </Card>
  );
}

function classificationLabel(value: string): string | null {
  switch (value) {
    case "HUMAN_REPLY":
      return "Human reply";
    case "OUT_OF_OFFICE":
      return "Out of office";
    case "BOUNCE":
      return "Bounce";
    case "OPT_OUT":
      return "Opt-out";
    case "AMBIGUOUS":
      return "Ambiguous match";
    case "OUTGOING":
      return null;
    default:
      return value;
  }
}

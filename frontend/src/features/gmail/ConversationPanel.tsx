import { useEffect, useMemo, useRef, useState } from "react";
import { useQueryClient } from "@tanstack/react-query";
import { Bot, CornerDownLeft, Sparkles } from "lucide-react";

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
import { useReplySuggestion } from "../../hooks/useIntelligence";
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

  const hasInbound = Boolean(
    summary?.items?.some((i) => i.direction === "INBOUND") || summary?.email_unread,
  );
  const suggestion = useReplySuggestion(leadId, hasInbound);
  const latestInbound = summary?.items?.find((i) => i.direction === "INBOUND");

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

      {suggestion.data && hasInbound ? (
        <Card className="border-indigo-200 bg-gradient-to-br from-indigo-50/60 via-white to-purple-50/40 p-4 shadow-xs">
          <div className="flex flex-wrap items-center justify-between gap-2">
            <div className="flex items-center gap-2">
              <Bot className="size-4 text-indigo-600" />
              <h3 className="text-small font-bold text-indigo-950">Harvey Reply Handler</h3>
              <Badge tone={intentBadgeTone(suggestion.data.intent)}>{suggestion.data.intent}</Badge>
              <Badge tone="gray">
                {suggestion.data.sentiment} ({Math.round(suggestion.data.confidence * 100)}% conf)
              </Badge>
            </div>
            <span className="text-caption font-semibold text-indigo-700 bg-indigo-100/70 px-2 py-0.5 rounded-full">
              Suggested Stage: <strong>{suggestion.data.suggested_stage}</strong>
            </span>
          </div>

          <p className="mt-2 text-small text-gray-700">
            <strong>Analysis: </strong>
            {suggestion.data.summary}
          </p>
          <p className="mt-1 text-caption text-gray-600">
            <strong>Recommended Next Step: </strong>
            {suggestion.data.recommended_action}
          </p>

          {suggestion.data.suggested_response_body ? (
            <div className="mt-3 rounded-lg border border-indigo-100 bg-white/90 p-3 shadow-2xs">
              <div className="flex items-center justify-between gap-2 mb-1.5">
                <span className="text-caption font-semibold text-indigo-900 flex items-center gap-1">
                  <Sparkles className="size-3.5 text-indigo-600" />
                  Suggested Response (Objection Playbook)
                </span>
                <Button
                  type="button"
                  variant="ghost"
                  className="h-7 px-2 text-caption font-semibold text-indigo-700 hover:text-indigo-900"
                  onClick={() => {
                    if (latestInbound) {
                      setReplyToId(latestInbound.id);
                    }
                    setReplyBody(suggestion.data?.suggested_response_body || "");
                    notify("Inserted suggested response from Harvey handler.", "success");
                  }}
                >
                  <CornerDownLeft className="size-3.5 mr-1" />
                  Insert Suggested Reply
                </Button>
              </div>
              <p className="text-small text-gray-800 whitespace-pre-wrap italic bg-gray-50/50 p-2.5 rounded border border-gray-100">
                &ldquo;{suggestion.data.suggested_response_body}&rdquo;
              </p>
            </div>
          ) : null}
        </Card>
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

function intentBadgeTone(intent: string): "green" | "blue" | "orange" | "indigo" | "gray" {
  switch (intent) {
    case "Interested":
    case "Positive":
      return "green";
    case "Meeting Request":
      return "indigo";
    case "Question":
    case "Pricing":
      return "blue";
    case "Objection":
    case "Not Interested":
      return "orange";
    default:
      return "gray";
  }
}

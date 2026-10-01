import { useCallback, useState } from "react";
import { Link } from "react-router-dom";

import { useToast } from "../components/feedback/useToast";
import { PageHeader } from "../components/layout/PageHeader";
import { Badge } from "../components/ui/Badge";
import { Button } from "../components/ui/Button";
import { Card } from "../components/ui/Card";
import { Skeleton } from "../components/ui/Skeleton";
import { ConversationSheet } from "../features/outreach/ConversationSheet";
import { MessageList } from "../features/outreach/MessageList";
import type { OutreachMessageItem } from "../types/workspace";
import { useConnectGmail, useGmailStatus, useSyncGmail } from "../hooks/useGmail";
import { useOutreachMessages } from "../hooks/useWorkspace";
import { apiErrorMessage } from "../lib/apiError";
import { cn, focusRing } from "../lib/cn";
import { formatWhen } from "../lib/format";
import type { GmailStatus } from "../services/gmail";

type View = "all" | "drafts" | "waiting" | "replied";

const views: { id: View; label: string; statuses?: string[] }[] = [
  { id: "all", label: "All" },
  { id: "drafts", label: "Drafts", statuses: ["DRAFT", "READY"] },
  { id: "waiting", label: "Waiting", statuses: ["SENT", "OPENED"] },
  { id: "replied", label: "Replied", statuses: ["REPLIED"] },
];

export function OutreachPage() {
  const messages = useOutreachMessages();
  const gmail = useGmailStatus();
  const [view, setView] = useState<View>("all");
  const [openThread, setOpenThread] = useState<OutreachMessageItem | null>(null);
  const closeThread = useCallback(() => {
    setOpenThread(null);
  }, []);
  const items = messages.data ?? [];
  const counts: Record<View, number> = {
    all: items.length,
    drafts: items.filter((item) => item.status === "DRAFT" || item.status === "READY").length,
    waiting: items.filter((item) => item.status === "SENT" || item.status === "OPENED").length,
    replied: items.filter((item) => item.status === "REPLIED").length,
  };
  const selected = views.find((item) => item.id === view) ?? views[0];

  return (
    <>
      <PageHeader
        title="Outreach"
        description="Drafts written from each lead's audit. Open a record to read the full Gmail thread."
      />
      <GmailStrip status={gmail.data} pending={gmail.isPending} error={gmail.isError} />
      <div className="mt-4 grid gap-3 sm:grid-cols-3">
        <Count label="Drafts" value={messages.isPending ? null : counts.drafts} />
        <Count label="Waiting on a reply" value={messages.isPending ? null : counts.waiting} />
        <Count label="Replies" value={messages.isPending ? null : counts.replied} />
      </div>
      <div
        className="mt-6 flex flex-wrap gap-1 rounded-card bg-gray-100 p-1"
        role="tablist"
        aria-label="Outreach views"
      >
        {views.map((item) => {
          const active = item.id === view;
          return (
            <button
              key={item.id}
              type="button"
              role="tab"
              aria-selected={active}
              className={cn(
                "inline-flex min-h-10 items-center gap-2 rounded-control px-3 text-body font-medium",
                focusRing,
                active ? "bg-white text-ink shadow-sm" : "text-gray-600 hover:text-ink",
              )}
              onClick={() => {
                setView(item.id);
              }}
            >
              {item.label}
              <span
                className={cn(
                  "rounded-full px-1.5 text-caption font-semibold tabular-nums",
                  active ? "bg-primary-50 text-primary-700" : "bg-white text-gray-500",
                )}
              >
                {messages.isPending ? "—" : counts[item.id]}
              </span>
            </button>
          );
        })}
      </div>
      <div className="mt-4">
        <MessageList
          statuses={selected.statuses}
          onSelect={(item) => {
            setOpenThread(item);
          }}
        />
      </div>
      <ConversationSheet item={openThread} onClose={closeThread} />
    </>
  );
}

function Count({ label, value }: { label: string; value: number | null }) {
  return (
    <Card className="shadow-sm">
      <p className="text-caption font-semibold text-gray-500">{label}</p>
      {value === null ? (
        <Skeleton className="mt-2 h-8 w-12" />
      ) : (
        <p className="mt-2 text-h2 font-bold text-ink tabular-nums">{value}</p>
      )}
    </Card>
  );
}

function GmailStrip({
  status,
  pending,
  error,
}: {
  status: GmailStatus | undefined;
  pending: boolean;
  error: boolean;
}) {
  const { notify } = useToast();
  const connect = useConnectGmail();
  const sync = useSyncGmail();
  const ready = Boolean(status?.connected && !status.needs_reauth);

  return (
    <Card className="shadow-sm">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <h2 className="text-h4 font-semibold text-ink">Gmail</h2>
          <p className="mt-1 max-w-2xl text-small text-gray-600">
            {ready
              ? `Connected as ${status?.email}. Send with Gmail is on each draft. Sync pulls replies back onto the lead.`
              : "Connect Gmail to send drafts from this workspace and pull replies onto the matching lead."}
          </p>
        </div>
        {pending ? <Skeleton className="h-6 w-24" /> : null}
        {status ? <GmailBadge status={status} /> : null}
      </div>
      {error ? (
        <p className="mt-3 text-body text-danger" role="alert">
          Gmail status could not be loaded.
        </p>
      ) : null}
      {status ? (
        <dl className="mt-4 grid gap-3 sm:grid-cols-3">
          <Fact label="Account" value={status.email ?? "Not connected"} />
          <Fact
            label="Last sync"
            value={status.last_synced_at ? formatWhen(status.last_synced_at) : "Never"}
          />
          <Fact
            label="OAuth client"
            value={status.configured ? "Ready on the API" : "Missing on the API"}
          />
        </dl>
      ) : null}
      {status?.last_error ? (
        <p className="mt-3 text-small text-amber-800" role="status">
          Last sync error: {status.last_error}
        </p>
      ) : null}
      <div className="mt-4 flex flex-wrap gap-2">
        {status && !ready ? (
          <Button
            disabled={!status.configured || connect.isPending}
            isLoading={connect.isPending}
            onClick={() => {
              connect.mutate(undefined, {
                onSuccess: ({ authorization_url }) => {
                  window.location.href = authorization_url;
                },
                onError: (connectError) => {
                  notify(apiErrorMessage(connectError, "Could not start Gmail connection."), "danger");
                },
              });
            }}
          >
            {status.needs_reauth ? "Reconnect Gmail" : "Connect Gmail"}
          </Button>
        ) : null}
        {ready ? (
          <Button
            variant="secondary"
            isLoading={sync.isPending}
            onClick={() => {
              sync.mutate(undefined, {
                onSuccess: (result) => {
                  notify(
                    result.matched > 0
                      ? `Synced ${result.matched} repl${result.matched === 1 ? "y" : "ies"}.`
                      : `Mailbox checked. ${result.processed} message${result.processed === 1 ? "" : "s"} reviewed.`,
                    "success",
                  );
                },
                onError: (syncError) => {
                  notify(apiErrorMessage(syncError, "Gmail sync failed."), "danger");
                },
              });
            }}
          >
            Sync replies
          </Button>
        ) : null}
        <Link
          to="/settings"
          className={cn(
            "inline-flex h-10 items-center rounded-control px-3 text-body font-semibold text-primary-700",
            focusRing,
          )}
        >
          Gmail settings
        </Link>
      </div>
    </Card>
  );
}

function Fact({ label, value }: { label: string; value: string }) {
  return (
    <div>
      <dt className="text-caption font-semibold text-gray-500">{label}</dt>
      <dd className="mt-1 text-body text-ink">{value}</dd>
    </div>
  );
}

function GmailBadge({ status }: { status: GmailStatus }) {
  if (!status.configured) {
    return <Badge tone="orange">Not configured</Badge>;
  }
  if (status.needs_reauth) {
    return <Badge tone="orange">Needs reconnect</Badge>;
  }
  if (status.connected) {
    return <Badge tone="green">Connected</Badge>;
  }
  return <Badge>Not connected</Badge>;
}

import { useState } from "react";
import { Link } from "react-router-dom";
import { Check, ExternalLink, SkipForward } from "lucide-react";

import { EmptyState } from "../components/feedback/EmptyState";
import { QueryGate } from "../components/feedback/QueryGate";
import { useToast } from "../components/feedback/useToast";
import { PageHeader } from "../components/layout/PageHeader";
import { Badge } from "../components/ui/Badge";
import { Button } from "../components/ui/Button";
import { Card } from "../components/ui/Card";
import { Input } from "../components/ui/Input";
import { Textarea } from "../components/ui/Textarea";
import { useApprovalQueue } from "../hooks/usePipeline";
import { apiErrorMessage } from "../lib/apiError";
import type { QueueItem } from "../services/pipeline";

export function ApprovalsPage() {
  const { query, approve, skip } = useApprovalQueue();
  const { notify } = useToast();

  return (
    <>
      <PageHeader
        title="Approvals"
        description="Emails written for you and waiting for your go-ahead. Nothing here has been sent."
      />
      <QueryGate
        pending={query.isPending}
        error={query.error}
        onRetry={() => void query.refetch()}
        fallback="The approval queue could not be loaded."
        loadingLabel="Loading drafts"
      >
        {query.data && query.data.length === 0 ? (
          <EmptyState
            title="No drafts waiting"
            description="New drafts appear here after leads are audited and given a mockup. Check Automation to make sure it is running."
          />
        ) : (
          <ul className="space-y-4">
            {query.data?.map((item) => (
              <DraftCard
                key={item.id}
                item={item}
                busy={approve.isPending || skip.isPending}
                onApprove={(edits) =>
                  approve.mutate(
                    { id: item.id, ...edits },
                    {
                      onSuccess: () => notify(`Sent to ${item.business_name}.`, "success"),
                      onError: (error) =>
                        notify(apiErrorMessage(error, "That email was not sent."), "danger"),
                    },
                  )
                }
                onSkip={() =>
                  skip.mutate(item.id, {
                    onSuccess: () => notify("Draft skipped.", "info"),
                    onError: (error) => notify(apiErrorMessage(error, "Could not skip that."), "danger"),
                  })
                }
              />
            ))}
          </ul>
        )}
      </QueryGate>
    </>
  );
}

function DraftCard({
  item,
  busy,
  onApprove,
  onSkip,
}: {
  item: QueueItem;
  busy: boolean;
  onApprove: (edits: { subject: string; body: string }) => void;
  onSkip: () => void;
}) {
  const [subject, setSubject] = useState(item.subject ?? "");
  const [body, setBody] = useState(item.body ?? "");
  const blocked = item.blocked !== null || item.country_policy === "block";

  return (
    <li>
      <Card>
        <div className="flex flex-wrap items-start justify-between gap-3">
          <div className="min-w-0">
            <Link to={`/leads/${item.lead_id}`} className="text-h4 font-semibold text-ink hover:underline">
              {item.business_name}
            </Link>
            <p className="text-small text-gray-600">
              {[item.industry, item.country, item.email].filter(Boolean).join(" · ")}
            </p>
          </div>
          <div className="flex flex-wrap items-center gap-2">
            <Badge tone="indigo">Priority {item.priority}</Badge>
            {item.strategy_label ? <Badge tone="blue">{item.strategy_label}</Badge> : null}
            {item.lead_score !== null ? <Badge tone="gray">Score {item.lead_score}</Badge> : null}
            {item.country_policy === "manual" ? (
              <Badge tone="orange">Manual-only country</Badge>
            ) : null}
            {item.mockup_url ? (
              <a
                href={item.mockup_url}
                target="_blank"
                rel="noreferrer"
                className="inline-flex items-center gap-1 text-small font-medium text-primary hover:underline"
              >
                Mockup <ExternalLink className="size-3.5" aria-hidden />
              </a>
            ) : (
              <Badge tone="gray">No mockup link</Badge>
            )}
          </div>
        </div>

        {item.reasons.length > 0 ? (
          <p className="mt-2 text-small text-gray-600">Why now: {item.reasons.join(", ")}.</p>
        ) : null}
        {item.blocked ? (
          <p className="mt-3 text-small text-red-700" role="alert">
            Cannot be sent: {item.blocked}
          </p>
        ) : null}
        {item.problems.length > 0 ? (
          <p className="mt-3 text-small text-amber-800" role="status">
            Check before sending: {item.problems.join(", ")}.
          </p>
        ) : null}

        <div className="mt-4 space-y-3">
          <Input label="Subject" value={subject} onChange={(event) => setSubject(event.target.value)} />
          <Textarea label="Message" rows={9} value={body} onChange={(event) => setBody(event.target.value)} />
        </div>
        <p className="mt-2 text-small text-gray-600">
          An unsubscribe line and your postal address are added when it is sent.
        </p>

        <div className="mt-4 flex flex-wrap justify-end gap-2">
          <Button variant="ghost" onClick={onSkip} disabled={busy}>
            <SkipForward className="size-4" aria-hidden /> Skip
          </Button>
          <Button onClick={() => onApprove({ subject, body })} disabled={busy || blocked} isLoading={busy}>
            <Check className="size-4" aria-hidden /> Approve and send
          </Button>
        </div>
      </Card>
    </li>
  );
}

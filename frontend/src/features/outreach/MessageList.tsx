import { Link } from "react-router-dom";

import { EmptyState } from "../../components/feedback/EmptyState";
import { QueryGate } from "../../components/feedback/QueryGate";
import { Badge, StatusBadge } from "../../components/ui/Badge";
import { Card } from "../../components/ui/Card";
import { useOutreachMessages } from "../../hooks/useWorkspace";
import { cn, focusRing } from "../../lib/cn";
import { formatWhen } from "../../lib/format";
import type { OutreachMessageItem } from "../../types/workspace";

type MessageListProps = {
  leadId?: string;
};

export function MessageList({ leadId }: MessageListProps) {
  const messages = useOutreachMessages(leadId);

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
              ? "Drafts for this lead will show up here."
              : "Drafts you can edit before sending will show up here."
          }
        />
      ) : null}
      {messages.data && messages.data.length > 0 ? (
        <div className="space-y-4">
          {messages.data.map((item) => (
            <MessageCard key={item.id} item={item} />
          ))}
        </div>
      ) : null}
    </QueryGate>
  );
}

function MessageCard({ item }: { item: OutreachMessageItem }) {
  const when = item.replied_at ?? item.opened_at ?? item.sent_at ?? item.created_at;

  return (
    <Card>
      <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
        <div>
          <Link
            to={`/leads/${item.lead_id}`}
            className={cn("font-semibold text-ink hover:text-primary-700", focusRing)}
          >
            {item.business_name}
          </Link>
          <p className="mt-1 text-body text-ink">{item.subject || "No subject"}</p>
          <p className="mt-1 text-small text-gray-600">
            {[item.contact_name, item.channel, formatWhen(when)].filter(Boolean).join(" · ")}
          </p>
        </div>
        <div className="flex flex-wrap gap-2">
          {item.channel ? <Badge>{item.channel}</Badge> : null}
          <StatusBadge status={item.status} />
        </div>
      </div>
      {item.message ? (
        <p className="mt-4 whitespace-pre-wrap text-body text-gray-700">{item.message}</p>
      ) : null}
    </Card>
  );
}

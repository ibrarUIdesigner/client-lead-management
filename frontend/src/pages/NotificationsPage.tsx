import { useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import {
  CheckCheck,
  Check,
  ExternalLink,
  Filter,
  Trash2,
} from "lucide-react";

import { PageHeader } from "../components/layout/PageHeader";
import { Button } from "../components/ui/Button";
import { Card } from "../components/ui/Card";
import { Badge } from "../components/ui/Badge";
import { LoadingState } from "../components/feedback/LoadingState";
import { EmptyState } from "../components/feedback/EmptyState";
import { NotificationIcon } from "../features/notifications/NotificationDropdown";
import {
  useNotificationActions,
  useNotifications,
} from "../hooks/useNotifications";
import type { NotificationItem } from "../types/notification";
import { formatWhen } from "../lib/format";
import { cn } from "../lib/cn";

type FilterTab = "all" | "unread" | "read";

export function NotificationsPage() {
  const navigate = useNavigate();
  const [tab, setTab] = useState<FilterTab>("all");
  const [typeFilter, setTypeFilter] = useState<string>("all");

  const queryParams = {
    is_read: tab === "all" ? undefined : tab === "read",
    type: typeFilter === "all" ? undefined : typeFilter,
    limit: 100,
  };

  const { data, isLoading } = useNotifications(queryParams);
  const { markRead, markAllRead, removeNotification } = useNotificationActions();

  const items = data?.items ?? [];
  const unreadCount = data?.unread_count ?? 0;

  const handleItemClick = (item: NotificationItem) => {
    if (!item.is_read) {
      markRead.mutate(item.id);
    }
    if (item.action_url) {
      navigate(item.action_url);
    } else if (item.lead_id) {
      navigate(`/leads/${item.lead_id}?tab=outreach`);
    }
  };

  return (
    <div className="space-y-6">
      <PageHeader
        title="Notifications"
        description="Stay on top of new email replies, meeting requests, follow-ups, and sales activity."
        actions={
          <div className="flex items-center gap-2">
            {unreadCount > 0 ? (
              <Button
                variant="secondary"
                size="sm"
                onClick={() => markAllRead.mutate()}
                isLoading={markAllRead.isPending}
                className="gap-1.5 px-3"
              >
                <CheckCheck className="size-4" />
                <span>Mark all as read</span>
              </Button>
            ) : null}
            <Link to="/settings">
              <Button variant="ghost" size="sm" className="px-3">
                Push settings
              </Button>
            </Link>
          </div>
        }
      />

      {/* Filter Bar */}
      <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between rounded-card border border-gray-200 bg-white p-3 shadow-2xs">
        {/* Tab Filters */}
        <div className="flex items-center gap-1 rounded-control bg-gray-100/80 p-1">
          <button
            type="button"
            onClick={() => setTab("all")}
            className={cn(
              "rounded px-3 py-1 text-small font-medium transition-colors",
              tab === "all"
                ? "bg-white text-ink shadow-2xs"
                : "text-gray-600 hover:text-ink",
            )}
          >
            All
          </button>
          <button
            type="button"
            onClick={() => setTab("unread")}
            className={cn(
              "rounded px-3 py-1 text-small font-medium transition-colors flex items-center gap-1.5",
              tab === "unread"
                ? "bg-white text-ink shadow-2xs"
                : "text-gray-600 hover:text-ink",
            )}
          >
            <span>Unread</span>
            {unreadCount > 0 ? (
              <span className="rounded-full bg-primary-100 px-1.5 py-0.2 text-[11px] font-bold text-primary-700">
                {unreadCount}
              </span>
            ) : null}
          </button>
          <button
            type="button"
            onClick={() => setTab("read")}
            className={cn(
              "rounded px-3 py-1 text-small font-medium transition-colors",
              tab === "read"
                ? "bg-white text-ink shadow-2xs"
                : "text-gray-600 hover:text-ink",
            )}
          >
            Read
          </button>
        </div>

        {/* Type Filter */}
        <div className="flex items-center gap-2">
          <Filter className="size-4 text-gray-400" />
          <select
            value={typeFilter}
            onChange={(e) => setTypeFilter(e.target.value)}
            className="rounded-control border border-gray-200 bg-white px-2.5 py-1 text-small text-ink focus:border-primary-500 focus:outline-none"
          >
            <option value="all">All Types</option>
            <option value="NEW_EMAIL_REPLY">Email Replies</option>
            <option value="POSITIVE_REPLY">Interested Replies</option>
            <option value="MEETING_REQUEST">Meeting Requests</option>
            <option value="OBJECTION_REPLY">Objections & Pricing</option>
            <option value="FOLLOWUP_DUE">Follow-ups Due</option>
            <option value="MOCKUP_READY">Mockups Ready</option>
            <option value="RESEARCH_COMPLETE">Research Complete</option>
          </select>
        </div>
      </div>

      {/* Notifications List */}
      {isLoading ? (
        <LoadingState label="Loading notifications" />
      ) : items.length === 0 ? (
        <Card>
          <EmptyState
            title={tab === "unread" ? "No unread notifications" : "No notifications found"}
            description={
              tab === "unread"
                ? "You're all caught up! When prospects reply, notifications will arrive here."
                : "No notifications matched the selected filter."
            }
          />
        </Card>
      ) : (
        <div className="space-y-3">
          {items.map((item) => (
            <div
              key={item.id}
              className={cn(
                "rounded-card border bg-white p-4 shadow-2xs transition-all duration-150 cursor-pointer hover:shadow-subtle",
                !item.is_read
                  ? "border-primary-200 bg-blue-50/30 hover:bg-blue-50/50"
                  : "border-gray-200 hover:border-gray-300",
              )}
              onClick={() => handleItemClick(item)}
            >
              <div className="flex flex-col sm:flex-row sm:items-start justify-between gap-3">
                <div className="flex items-start gap-3 min-w-0">
                  <div className="shrink-0 mt-0.5">
                    <NotificationIcon type={item.type} priority={item.priority} />
                  </div>

                  <div className="min-w-0">
                    <div className="flex flex-wrap items-center gap-2">
                      <h3
                        className={cn(
                          "text-body truncate",
                          !item.is_read ? "font-bold text-ink" : "font-semibold text-gray-800",
                        )}
                      >
                        {item.title}
                      </h3>
                      {!item.is_read ? (
                        <span className="rounded bg-primary-100 px-1.5 py-0.5 text-[11px] font-bold text-primary-700">
                          NEW
                        </span>
                      ) : null}
                      {item.priority === "URGENT" ? (
                        <Badge tone="red">Urgent</Badge>
                      ) : item.priority === "HIGH" ? (
                        <Badge tone="orange">High</Badge>
                      ) : null}
                    </div>

                    <p className="mt-1 text-small leading-relaxed text-gray-700 line-clamp-2">
                      {item.message}
                    </p>

                    <div className="mt-2.5 flex flex-wrap items-center gap-3 text-caption text-gray-500">
                      <span>{formatWhen(item.created_at)}</span>
                      {item.metadata?.sender_email ? (
                        <span className="font-mono text-[11px] text-gray-600">
                          {String(item.metadata.sender_email)}
                        </span>
                      ) : null}
                    </div>
                  </div>
                </div>

                {/* Right actions */}
                <div
                  className="flex items-center gap-2 self-end sm:self-center shrink-0"
                  onClick={(e) => e.stopPropagation()}
                >
                  {!item.is_read ? (
                    <Button
                      variant="ghost"
                      onClick={() => markRead.mutate(item.id)}
                      className="text-gray-500 hover:text-ink gap-1 h-8 px-2 text-small"
                      title="Mark read"
                    >
                      <Check className="size-3.5" />
                      <span className="text-caption">Mark read</span>
                    </Button>
                  ) : null}

                  <Button
                    variant="ghost"
                    size="icon"
                    onClick={() => removeNotification.mutate(item.id)}
                    className="text-gray-400 hover:text-danger h-8 w-8"
                    title="Delete notification"
                  >
                    <Trash2 className="size-4" />
                  </Button>

                  <Button
                    variant="secondary"
                    onClick={() => handleItemClick(item)}
                    className="gap-1 h-8 px-2.5 text-small"
                  >
                    <span>View</span>
                    <ExternalLink className="size-3.5" />
                  </Button>
                </div>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

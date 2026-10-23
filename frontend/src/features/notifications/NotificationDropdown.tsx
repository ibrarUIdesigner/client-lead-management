import { useRef, useEffect } from "react";
import { Link, useNavigate } from "react-router-dom";
import {
  Bell,
  Calendar,
  CheckCheck,
  Clock,
  ExternalLink,
  Flame,
  MessageSquare,
  Sparkles,
  Trash2,
  AlertTriangle,
} from "lucide-react";

import { useNotificationActions, useNotifications } from "../../hooks/useNotifications";
import type { NotificationItem } from "../../types/notification";
import { cn } from "../../lib/cn";
import { formatWhen } from "../../lib/format";

interface NotificationDropdownProps {
  open: boolean;
  onClose: () => void;
}

export function NotificationDropdown({ open, onClose }: NotificationDropdownProps) {
  const navigate = useNavigate();
  const dropdownRef = useRef<HTMLDivElement>(null);

  const { data, isLoading } = useNotifications({ limit: 15 });
  const { markRead, markAllRead, removeNotification } = useNotificationActions();

  const notifications = data?.items ?? [];
  const unreadCount = data?.unread_count ?? 0;

  // Handle outside click & escape key
  useEffect(() => {
    if (!open) return;

    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === "Escape") onClose();
    };

    const handleClickOutside = (e: MouseEvent) => {
      if (dropdownRef.current && !dropdownRef.current.contains(e.target as Node)) {
        onClose();
      }
    };

    document.addEventListener("keydown", handleKeyDown);
    document.addEventListener("mousedown", handleClickOutside);
    return () => {
      document.removeEventListener("keydown", handleKeyDown);
      document.removeEventListener("mousedown", handleClickOutside);
    };
  }, [open, onClose]);

  if (!open) return null;

  const handleClickItem = (item: NotificationItem) => {
    if (!item.is_read) {
      markRead.mutate(item.id);
    }
    onClose();
    if (item.action_url) {
      navigate(item.action_url);
    } else if (item.lead_id) {
      navigate(`/leads/${item.lead_id}?tab=outreach`);
    }
  };

  return (
    <div
      ref={dropdownRef}
      className="absolute right-0 top-full mt-2 w-80 sm:w-96 rounded-xl border border-gray-200 bg-white shadow-xl z-50 overflow-hidden animate-in fade-in slide-in-from-top-2 duration-150"
      role="dialog"
      aria-label="Notifications"
    >
      {/* Header */}
      <div className="flex items-center justify-between border-b border-gray-100 px-4 py-3 bg-gray-50/70">
        <div className="flex items-center gap-2">
          <h3 className="text-small font-bold text-ink">Notifications</h3>
          {unreadCount > 0 ? (
            <span className="rounded-full bg-primary-100 px-2 py-0.5 text-[11px] font-semibold text-primary-700">
              {unreadCount} unread
            </span>
          ) : null}
        </div>

        <div className="flex items-center gap-2">
          {unreadCount > 0 ? (
            <button
              type="button"
              onClick={() => markAllRead.mutate()}
              disabled={markAllRead.isPending}
              className="text-[12px] font-medium text-primary-700 hover:text-primary-800 flex items-center gap-1 transition-colors"
              title="Mark all as read"
            >
              <CheckCheck className="size-3.5" />
              <span>Mark all read</span>
            </button>
          ) : null}
        </div>
      </div>

      {/* Body List */}
      <div className="max-h-[22rem] overflow-y-auto divide-y divide-gray-100">
        {isLoading ? (
          <div className="py-8 text-center text-small text-gray-500">
            <div className="inline-block size-5 animate-spin rounded-full border-2 border-primary-600 border-t-transparent" />
            <p className="mt-2">Loading notifications...</p>
          </div>
        ) : notifications.length === 0 ? (
          <div className="py-10 text-center px-4">
            <Bell className="mx-auto size-8 text-gray-300" />
            <p className="mt-2 text-small font-medium text-ink">No notifications yet</p>
            <p className="mt-1 text-caption text-gray-500">
              Inbound replies, follow-ups, and alerts will appear here.
            </p>
          </div>
        ) : (
          notifications.map((item) => (
            <div
              key={item.id}
              onClick={() => handleClickItem(item)}
              className={cn(
                "group relative flex items-start gap-3 p-3.5 transition-colors cursor-pointer text-left",
                !item.is_read
                  ? "bg-blue-50/50 hover:bg-blue-50/80"
                  : "bg-white hover:bg-gray-50/90",
              )}
            >
              {/* Icon badge */}
              <div className="shrink-0 mt-0.5">
                <NotificationIcon type={item.type} priority={item.priority} />
              </div>

              {/* Content */}
              <div className="flex-1 min-w-0 pr-6">
                <div className="flex items-center gap-1.5">
                  <p
                    className={cn(
                      "text-small truncate",
                      !item.is_read ? "font-semibold text-ink" : "font-medium text-gray-800",
                    )}
                  >
                    {item.title}
                  </p>
                  {!item.is_read ? (
                    <span className="size-2 rounded-full bg-primary-600 shrink-0" />
                  ) : null}
                </div>

                <p className="mt-0.5 text-caption text-gray-600 line-clamp-2 leading-relaxed">
                  {item.message}
                </p>

                <div className="mt-1.5 flex items-center gap-2 text-[11px] text-gray-400">
                  <span>{formatWhen(item.created_at)}</span>
                  {item.priority === "URGENT" ? (
                    <span className="font-semibold text-red-600">Urgent</span>
                  ) : null}
                </div>
              </div>

              {/* Delete button (hover) */}
              <button
                type="button"
                onClick={(e) => {
                  e.stopPropagation();
                  removeNotification.mutate(item.id);
                }}
                className="absolute right-2 top-3 opacity-0 group-hover:opacity-100 p-1 text-gray-400 hover:text-danger rounded hover:bg-gray-100 transition-opacity"
                title="Delete notification"
              >
                <Trash2 className="size-3.5" />
              </button>
            </div>
          ))
        )}
      </div>

      {/* Footer */}
      <div className="border-t border-gray-100 bg-gray-50/50 p-2 text-center">
        <Link
          to="/notifications"
          onClick={onClose}
          className="inline-flex items-center justify-center gap-1 w-full rounded py-1.5 text-small font-medium text-primary-700 hover:text-primary-800 hover:bg-white transition-colors"
        >
          <span>View all notifications</span>
          <ExternalLink className="size-3.5" />
        </Link>
      </div>
    </div>
  );
}

export function NotificationIcon({
  type,
  priority,
}: {
  type: string;
  priority?: string;
}) {
  if (type === "POSITIVE_REPLY" || priority === "HIGH") {
    return (
      <div className="flex size-7 items-center justify-center rounded-full bg-amber-100 text-amber-600">
        <Flame className="size-4" />
      </div>
    );
  }

  if (type === "MEETING_REQUEST" || priority === "URGENT") {
    return (
      <div className="flex size-7 items-center justify-center rounded-full bg-emerald-100 text-emerald-600">
        <Calendar className="size-4" />
      </div>
    );
  }

  if (type === "OBJECTION_REPLY") {
    return (
      <div className="flex size-7 items-center justify-center rounded-full bg-orange-100 text-orange-600">
        <AlertTriangle className="size-4" />
      </div>
    );
  }

  if (type === "FOLLOWUP_DUE") {
    return (
      <div className="flex size-7 items-center justify-center rounded-full bg-purple-100 text-purple-600">
        <Clock className="size-4" />
      </div>
    );
  }

  if (type === "MOCKUP_READY") {
    return (
      <div className="flex size-7 items-center justify-center rounded-full bg-sky-100 text-sky-600">
        <Sparkles className="size-4" />
      </div>
    );
  }

  return (
    <div className="flex size-7 items-center justify-center rounded-full bg-blue-100 text-blue-600">
      <MessageSquare className="size-4" />
    </div>
  );
}

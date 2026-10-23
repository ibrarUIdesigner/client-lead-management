import { useState } from "react";
import { Bell } from "lucide-react";

import { useUnreadNotificationsCount } from "../../hooks/useNotifications";
import { Button } from "../../components/ui/Button";
import { NotificationDropdown } from "./NotificationDropdown";
import { cn } from "../../lib/cn";

export function NotificationBell() {
  const [open, setOpen] = useState(false);
  const { data: unreadCount = 0 } = useUnreadNotificationsCount();

  return (
    <div className="relative inline-flex items-center">
      <Button
        variant="ghost"
        size="icon"
        className={cn(
          "relative h-9 w-9 text-gray-600 hover:text-ink transition-colors",
          open && "bg-gray-100 text-ink",
        )}
        aria-label={`Notifications${unreadCount > 0 ? `, ${unreadCount} unread` : ""}`}
        aria-expanded={open}
        onClick={() => setOpen((prev) => !prev)}
      >
        <Bell className="size-4.5" aria-hidden="true" />
        {unreadCount > 0 ? (
          <span
            className="absolute -top-1 -right-1 flex h-4 min-w-4 items-center justify-center rounded-full bg-danger px-1 text-[10px] font-bold text-white shadow-xs animate-in zoom-in-75 duration-150"
            aria-hidden="true"
          >
            {unreadCount > 99 ? "99+" : unreadCount}
          </span>
        ) : null}
      </Button>

      <NotificationDropdown open={open} onClose={() => setOpen(false)} />
    </div>
  );
}

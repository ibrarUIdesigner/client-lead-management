import { Inbox, type LucideIcon } from "lucide-react";
import type { ReactNode } from "react";
import { cn } from "../../lib/cn";

type EmptyStateProps = {
  title: string;
  description: string;
  action?: ReactNode;
  compact?: boolean;
  icon?: LucideIcon;
  align?: "center" | "start";
};

export function EmptyState({
  title,
  description,
  action,
  compact = false,
  icon: Icon = Inbox,
  align = "center",
}: EmptyStateProps) {
  const isCenter = align === "center";

  return (
    <div
      className={cn(
        "flex flex-col rounded-card border border-dashed border-gray-200/90 bg-gray-50/40 transition-colors",
        isCenter ? "items-center text-center mx-auto" : "items-start text-left",
        compact ? "p-4 gap-2.5 max-w-lg" : "p-8 sm:p-12 gap-3 max-w-xl",
      )}
    >
      <span className="inline-flex size-11 items-center justify-center rounded-full bg-white shadow-2xs border border-gray-200/80 text-gray-400">
        <Icon className="size-5" aria-hidden="true" />
      </span>
      <h3
        className={cn(
          "font-semibold text-ink",
          compact ? "text-body-lg" : "text-h3 font-bold tracking-tight",
        )}
      >
        {title}
      </h3>
      <p
        className={cn(
          "text-body text-gray-500 leading-relaxed",
          isCenter ? "max-w-md" : "max-w-lg",
        )}
      >
        {description}
      </p>
      {action ? <div className="mt-2 flex flex-wrap gap-2">{action}</div> : null}
    </div>
  );
}

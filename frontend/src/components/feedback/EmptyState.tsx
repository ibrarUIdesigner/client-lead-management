import { Inbox, type LucideIcon } from "lucide-react";
import type { ReactNode } from "react";

type EmptyStateProps = {
  title: string;
  description: string;
  action?: ReactNode;
  compact?: boolean;
  icon?: LucideIcon;
};

export function EmptyState({
  title,
  description,
  action,
  compact = false,
  icon: Icon = Inbox,
}: EmptyStateProps) {
  return (
    <div
      className={
        compact
          ? "flex flex-col items-start gap-2 rounded-card border border-dashed border-gray-300 bg-white px-4 py-4"
          : "flex flex-col items-start gap-3 rounded-card border border-dashed border-gray-300 bg-white px-4 py-8 sm:px-6 sm:py-10"
      }
    >
      <span className="inline-flex size-10 items-center justify-center rounded-full bg-gray-100 text-gray-500">
        <Icon className="size-5" aria-hidden="true" />
      </span>
      <h2 className={compact ? "text-h4 font-semibold text-ink" : "text-h3 font-semibold text-ink"}>
        {title}
      </h2>
      <p className="max-w-lg text-body leading-normal text-gray-600">{description}</p>
      {action}
    </div>
  );
}

import type { ReactNode } from "react";

type EmptyStateProps = {
  title: string;
  description: string;
  action?: ReactNode;
  compact?: boolean;
};

export function EmptyState({ title, description, action, compact = false }: EmptyStateProps) {
  return (
    <div
      className={
        compact
          ? "flex flex-col items-start gap-2 rounded-card border border-dashed border-gray-300 bg-white px-4 py-4"
          : "flex flex-col items-start gap-3 rounded-card border border-dashed border-gray-300 bg-white px-6 py-10"
      }
    >
      <h2 className={compact ? "text-h4 font-semibold text-ink" : "text-h3 font-semibold text-ink"}>
        {title}
      </h2>
      <p className="max-w-lg text-body text-gray-600">{description}</p>
      {action}
    </div>
  );
}

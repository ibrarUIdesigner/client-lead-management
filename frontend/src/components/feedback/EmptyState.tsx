import type { ReactNode } from "react";

type EmptyStateProps = {
  title: string;
  description: string;
  action?: ReactNode;
};

export function EmptyState({ title, description, action }: EmptyStateProps) {
  return (
    <div className="flex flex-col items-start gap-3 rounded-card border border-dashed border-gray-300 bg-white px-6 py-10">
      <h2 className="text-h3 font-semibold text-ink">{title}</h2>
      <p className="max-w-lg text-body text-gray-600">{description}</p>
      {action}
    </div>
  );
}

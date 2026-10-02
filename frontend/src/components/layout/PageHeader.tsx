import type { ReactNode } from "react";

type PageHeaderProps = {
  title: string;
  description?: string;
  actions?: ReactNode;
};

export function PageHeader({ title, description, actions }: PageHeaderProps) {
  return (
    <div className="mb-6 flex flex-col gap-4 sm:mb-8 md:flex-row md:items-end md:justify-between">
      <div className="min-w-0">
        <h1 className="text-h1 font-bold text-balance break-words text-ink">{title}</h1>
        {description ? (
          <p className="mt-2 max-w-2xl text-pretty text-body leading-relaxed text-gray-600 md:text-body-lg">
            {description}
          </p>
        ) : null}
      </div>
      {actions ? (
        <div className="flex w-full flex-col gap-2 sm:w-auto sm:flex-row sm:flex-wrap sm:items-center [&_button]:w-full sm:[&_button]:w-auto">
          {actions}
        </div>
      ) : null}
    </div>
  );
}

import type { ReactNode } from "react";

import { cn } from "../../lib/cn";
import { describedBy } from "../../lib/describedBy";

type FieldProps = {
  id: string;
  label: string;
  hint?: string;
  error?: string;
  hideLabel?: boolean;
  children: ReactNode;
};

export function Field({ id, label, hint, error, hideLabel = false, children }: FieldProps) {
  const descriptionId = describedBy(id, hint, error);

  return (
    <div className={cn("flex flex-col", hideLabel ? "" : "gap-1.5")}>
      <label
        htmlFor={id}
        className={hideLabel ? "sr-only" : "text-small font-medium text-gray-700"}
      >
        {label}
      </label>
      {children}
      {error ? (
        <p id={descriptionId} className="text-small text-danger mt-1" role="alert">
          {error}
        </p>
      ) : null}
      {!error && hint ? (
        <p id={descriptionId} className="text-small text-gray-500 mt-1">
          {hint}
        </p>
      ) : null}
    </div>
  );
}

import type { ReactNode } from "react";

import { describedBy } from "../../lib/describedBy";

type FieldProps = {
  id: string;
  label: string;
  hint?: string;
  error?: string;
  children: ReactNode;
};

export function Field({ id, label, hint, error, children }: FieldProps) {
  const descriptionId = describedBy(id, hint, error);

  return (
    <div className="flex flex-col gap-2">
      <label htmlFor={id} className="text-small font-medium text-gray-700">
        {label}
      </label>
      {children}
      {error ? (
        <p id={descriptionId} className="text-small text-danger" role="alert">
          {error}
        </p>
      ) : null}
      {!error && hint ? (
        <p id={descriptionId} className="text-small text-gray-500">
          {hint}
        </p>
      ) : null}
    </div>
  );
}

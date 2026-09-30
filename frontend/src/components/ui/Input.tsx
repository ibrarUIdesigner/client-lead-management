import { useId, type InputHTMLAttributes } from "react";

import { cn, focusRing } from "../../lib/cn";
import { describedBy } from "../../lib/describedBy";
import { Field } from "./Field";

type InputProps = Omit<InputHTMLAttributes<HTMLInputElement>, "id"> & {
  id?: string;
  label: string;
  hint?: string;
  error?: string;
};

export function Input({ id, label, hint, error, className, ...props }: InputProps) {
  const generatedId = useId();
  const inputId = id ?? generatedId;

  return (
    <Field id={inputId} label={label} hint={hint} error={error}>
      <input
        id={inputId}
        aria-invalid={error ? true : undefined}
        aria-describedby={describedBy(inputId, hint, error)}
        className={cn(
          "h-11 w-full rounded-control border border-gray-300 bg-white px-3 text-body text-ink lg:h-10",
          focusRing,
          error ? "border-danger" : "focus-visible:border-primary-500",
          className,
        )}
        {...props}
      />
    </Field>
  );
}

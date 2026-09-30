import { useId, type TextareaHTMLAttributes } from "react";

import { cn, focusRing } from "../../lib/cn";
import { describedBy } from "../../lib/describedBy";
import { Field } from "./Field";

type TextareaProps = Omit<TextareaHTMLAttributes<HTMLTextAreaElement>, "id"> & {
  id?: string;
  label: string;
  hint?: string;
  error?: string;
};

export function Textarea({ id, label, hint, error, className, ...props }: TextareaProps) {
  const generatedId = useId();
  const inputId = id ?? generatedId;

  return (
    <Field id={inputId} label={label} hint={hint} error={error}>
      <textarea
        id={inputId}
        aria-invalid={error ? true : undefined}
        aria-describedby={describedBy(inputId, hint, error)}
        className={cn(
          "min-h-28 w-full resize-y rounded-control border border-gray-300 bg-white px-3 py-2 text-body text-ink",
          focusRing,
          error ? "border-danger" : "focus-visible:border-primary-500",
          className,
        )}
        {...props}
      />
    </Field>
  );
}

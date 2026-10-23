import { useId, type InputHTMLAttributes, type ReactNode } from "react";

import { cn, focusRing } from "../../lib/cn";
import { describedBy } from "../../lib/describedBy";
import { Field } from "./Field";

type InputProps = Omit<InputHTMLAttributes<HTMLInputElement>, "id"> & {
  id?: string;
  label: string;
  hint?: string;
  error?: string;
  leftIcon?: ReactNode;
  rightElement?: ReactNode;
};

export function Input({
  id,
  label,
  hint,
  error,
  leftIcon,
  rightElement,
  className,
  ...props
}: InputProps) {
  const generatedId = useId();
  const inputId = id ?? generatedId;

  return (
    <Field id={inputId} label={label} hint={hint} error={error}>
      <div className="relative flex items-center">
        {leftIcon ? (
          <span className="pointer-events-none absolute left-3 flex items-center text-gray-400">
            {leftIcon}
          </span>
        ) : null}
        <input
          id={inputId}
          aria-invalid={error ? true : undefined}
          aria-describedby={describedBy(inputId, hint, error)}
          className={cn(
            "h-11 w-full rounded-control border border-gray-300 bg-white px-3 text-body text-ink transition-colors placeholder:text-gray-400 lg:h-10",
            focusRing,
            leftIcon ? "pl-9" : "",
            rightElement ? "pr-10" : "",
            error
              ? "border-danger focus-visible:border-danger"
              : "focus-visible:border-primary-500",
            className,
          )}
          {...props}
        />
        {rightElement ? (
          <div className="absolute right-2.5 flex items-center">{rightElement}</div>
        ) : null}
      </div>
    </Field>
  );
}

import { useId, type SelectHTMLAttributes } from "react";

import { cn, focusRing } from "../../lib/cn";
import { describedBy } from "../../lib/describedBy";
import { Field } from "./Field";

export type SelectOption = {
  value: string;
  label: string;
};

type SelectProps = Omit<SelectHTMLAttributes<HTMLSelectElement>, "id"> & {
  id?: string;
  label: string;
  hint?: string;
  error?: string;
  options: SelectOption[];
  placeholder?: string;
};

export function Select({
  id,
  label,
  hint,
  error,
  options,
  placeholder,
  className,
  ...props
}: SelectProps) {
  const generatedId = useId();
  const inputId = id ?? generatedId;

  return (
    <Field id={inputId} label={label} hint={hint} error={error}>
      <select
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
      >
        {placeholder ? <option value="">{placeholder}</option> : null}
        {options.map((option) => (
          <option key={option.value} value={option.value}>
            {option.label}
          </option>
        ))}
      </select>
    </Field>
  );
}

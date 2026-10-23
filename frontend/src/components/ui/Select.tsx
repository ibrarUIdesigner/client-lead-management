import { useId, type SelectHTMLAttributes } from "react";
import { ChevronDown } from "lucide-react";

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
  hideLabel?: boolean;
};

export function Select({
  id,
  label,
  hint,
  error,
  options,
  placeholder,
  hideLabel,
  className,
  ...props
}: SelectProps) {
  const generatedId = useId();
  const inputId = id ?? generatedId;

  return (
    <Field id={inputId} label={label} hint={hint} error={error} hideLabel={hideLabel}>
      <div className="relative flex items-center">
        <select
          id={inputId}
          aria-invalid={error ? true : undefined}
          aria-describedby={describedBy(inputId, hint, error)}
          className={cn(
            "h-11 w-full appearance-none rounded-control border border-gray-300 bg-white pr-9 pl-3 text-body text-ink shadow-2xs transition-all hover:border-gray-400/80 lg:h-10",
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
        <ChevronDown
          className="pointer-events-none absolute right-3 size-4 text-gray-400"
          aria-hidden="true"
        />
      </div>
    </Field>
  );
}

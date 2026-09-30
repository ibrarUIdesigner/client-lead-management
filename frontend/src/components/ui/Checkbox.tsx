import { useId, type InputHTMLAttributes } from "react";

import { focusRing } from "../../lib/cn";

type CheckboxProps = Omit<InputHTMLAttributes<HTMLInputElement>, "type" | "id"> & {
  id?: string;
  label: string;
};

export function Checkbox({ id, label, className, ...props }: CheckboxProps) {
  const generatedId = useId();
  const inputId = id ?? generatedId;

  return (
    <label htmlFor={inputId} className="inline-flex min-h-11 items-center gap-3 text-body text-ink">
      <input
        id={inputId}
        type="checkbox"
        className={`size-4 accent-primary ${focusRing} ${className ?? ""}`}
        {...props}
      />
      {label}
    </label>
  );
}

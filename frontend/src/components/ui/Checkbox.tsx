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
    <label htmlFor={inputId} className="inline-flex min-h-10 cursor-pointer items-center gap-2.5 text-body font-medium text-ink select-none">
      <input
        id={inputId}
        type="checkbox"
        className={`size-4 rounded-xs accent-primary cursor-pointer ${focusRing} ${className ?? ""}`}
        {...props}
      />
      {label}
    </label>
  );
}

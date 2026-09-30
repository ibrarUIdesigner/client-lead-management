import { useId } from "react";

import { cn, focusRing } from "../../lib/cn";

type SwitchProps = {
  label: string;
  checked: boolean;
  onCheckedChange: (checked: boolean) => void;
  disabled?: boolean;
};

export function Switch({ label, checked, onCheckedChange, disabled = false }: SwitchProps) {
  const id = useId();

  return (
    <div className="flex min-h-11 items-center justify-between gap-4">
      <span id={id} className="text-body text-ink">
        {label}
      </span>
      <button
        type="button"
        role="switch"
        aria-checked={checked}
        aria-labelledby={id}
        disabled={disabled}
        onClick={() => {
          onCheckedChange(!checked);
        }}
        className={cn(
          "relative h-6 w-11 shrink-0 rounded-full transition-colors duration-150 disabled:opacity-50",
          focusRing,
          checked ? "bg-primary" : "bg-gray-300",
        )}
      >
        <span
          aria-hidden="true"
          className={cn(
            "absolute top-0.5 size-5 rounded-full bg-white shadow-sm transition-transform duration-150",
            checked ? "translate-x-5" : "translate-x-0.5",
          )}
        />
      </button>
    </div>
  );
}

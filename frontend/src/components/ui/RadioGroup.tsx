import { useId } from "react";

import { focusRing } from "../../lib/cn";

export type RadioOption = {
  value: string;
  label: string;
};

type RadioGroupProps = {
  label: string;
  name: string;
  value: string;
  options: RadioOption[];
  onChange: (value: string) => void;
};

export function RadioGroup({ label, name, value, options, onChange }: RadioGroupProps) {
  const groupId = useId();

  return (
    <fieldset className="flex flex-col gap-2">
      <legend className="text-small font-medium text-gray-700">{label}</legend>
      {options.map((option) => {
        const optionId = `${groupId}-${option.value}`;

        return (
          <label
            key={option.value}
            htmlFor={optionId}
            className="inline-flex min-h-11 items-center gap-3 text-body text-ink"
          >
            <input
              id={optionId}
              type="radio"
              name={name}
              value={option.value}
              checked={value === option.value}
              onChange={() => {
                onChange(option.value);
              }}
              className={`size-4 accent-primary ${focusRing}`}
            />
            {option.label}
          </label>
        );
      })}
    </fieldset>
  );
}

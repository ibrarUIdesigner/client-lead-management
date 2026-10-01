import { useRef, useState, type FormEvent, type ReactNode } from "react";

import { Button } from "../../components/ui/Button";
import { Checkbox } from "../../components/ui/Checkbox";
import { Input } from "../../components/ui/Input";
import { Modal } from "../../components/ui/Modal";
import { Select } from "../../components/ui/Select";
import { Textarea } from "../../components/ui/Textarea";
import { useStartApifyRun } from "../../hooks/useApify";
import { apiErrorMessage } from "../../lib/apiError";
import type { ApifyConnector, ApifyField } from "../../types/apify";
import { buildRunWrite, initialFieldValue, type FieldValue } from "./runInput";

type RunActorDialogProps = {
  connector: ApifyConnector;
  open: boolean;
  onClose: () => void;
  onStarted: (runId: string) => void;
};

export function RunActorDialog({ connector, open, onClose, onStarted }: RunActorDialogProps) {
  const start = useStartApifyRun();
  const [values, setValues] = useState<Record<string, FieldValue>>(() => fieldValues(connector));
  const [maxItems, setMaxItems] = useState("");
  const [spendingCap, setSpendingCap] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const requestId = useRef(crypto.randomUUID());

  async function onSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (submitting) {
      return;
    }
    const built = buildRunWrite(connector, values, maxItems, spendingCap, requestId.current);
    if ("error" in built) {
      setError(built.error);
      return;
    }
    setSubmitting(true);
    setError(null);
    try {
      const run = await start.mutateAsync({
        connectorId: connector.id,
        payload: built.payload,
      });
      onStarted(run.id);
      onClose();
    } catch (caught) {
      requestId.current = crypto.randomUUID();
      setError(apiErrorMessage(caught, "The actor could not be started."));
      setSubmitting(false);
    }
  }

  const searchFields = connector.fields.filter((field) => field.group === "search");
  const limitFields = connector.fields.filter((field) => field.group === "limit");
  const otherFields = connector.fields.filter((field) => field.group === "other");

  return (
    <Modal
      open={open}
      title={`Run ${connector.display_name}`}
      description="Starting a run can spend Apify credit. Set a spending cap when you want a hard stop."
      onClose={onClose}
    >
      <form className="max-h-[70vh] space-y-6 overflow-y-auto pr-1" onSubmit={onSubmit} noValidate>
        <div className="rounded-card border border-gray-200 bg-gray-50 px-4 py-3">
          <p className="text-small font-medium text-gray-700">Pricing</p>
          <p className="mt-1 text-body text-ink">{connector.pricing.label}</p>
          {connector.pricing.details.map((line) => (
            <p key={line} className="mt-1 text-small text-gray-600">
              {line}
            </p>
          ))}
        </div>

        <FieldGroup
          title="Search filters"
          fields={searchFields}
          values={values}
          onChange={setValues}
        />
        <FieldGroup
          title="Result limits"
          fields={limitFields}
          values={values}
          onChange={setValues}
          extra={
            connector.pricing.supports_max_items ? (
              <Input
                label="Charged result limit"
                hint="Caps how many results you are charged for. The actor may still return a different number."
                inputMode="numeric"
                value={maxItems}
                onChange={(event) => {
                  setMaxItems(event.target.value);
                }}
              />
            ) : null
          }
        />
        <FieldGroup title="Other input" fields={otherFields} values={values} onChange={setValues} />

        {connector.pricing.supports_max_charge ? (
          <Input
            label="Spending cap (USD)"
            hint={
              connector.pricing.minimal_max_total_charge_usd
                ? `Optional. Apify stops the run at this total. Minimum $${connector.pricing.minimal_max_total_charge_usd.toFixed(2)}.`
                : "Optional. Apify stops the run when the total charge reaches this amount."
            }
            inputMode="decimal"
            value={spendingCap}
            onChange={(event) => {
              setSpendingCap(event.target.value);
            }}
          />
        ) : null}

        {connector.fields.length === 0 ? (
          <p className="text-body text-gray-600">This actor does not publish input fields.</p>
        ) : null}

        {error ? (
          <p className="text-small text-danger" role="alert">
            {error}
          </p>
        ) : null}
        <div className="flex justify-end gap-2">
          <Button variant="secondary" onClick={onClose} disabled={submitting}>
            Cancel
          </Button>
          <Button type="submit" isLoading={submitting}>
            Start run
          </Button>
        </div>
      </form>
    </Modal>
  );
}

function fieldValues(connector: ApifyConnector): Record<string, FieldValue> {
  const next: Record<string, FieldValue> = {};
  for (const field of connector.fields) {
    next[field.key] = initialFieldValue(field);
  }
  return next;
}

function FieldGroup({
  title,
  fields,
  values,
  onChange,
  extra,
}: {
  title: string;
  fields: ApifyField[];
  values: Record<string, FieldValue>;
  onChange: (values: Record<string, FieldValue>) => void;
  extra?: ReactNode;
}) {
  if (fields.length === 0 && !extra) {
    return null;
  }
  return (
    <fieldset className="space-y-4">
      <legend className="text-h4 font-semibold text-ink">{title}</legend>
      {fields.map((field) => (
        <FieldControl
          key={field.key}
          field={field}
          value={values[field.key] ?? initialFieldValue(field)}
          onChange={(value) => {
            onChange({ ...values, [field.key]: value });
          }}
        />
      ))}
      {extra}
    </fieldset>
  );
}

function FieldControl({
  field,
  value,
  onChange,
}: {
  field: ApifyField;
  value: FieldValue;
  onChange: (value: FieldValue) => void;
}) {
  const text = typeof value === "string" ? value : "";
  const hint = field.description ?? undefined;
  const label = field.required ? `${field.label}` : field.label;

  if (field.field_type === "boolean") {
    return (
      <Checkbox
        label={label}
        checked={value === true}
        onChange={(event) => {
          onChange(event.target.checked);
        }}
      />
    );
  }
  if (field.field_type === "enum" && field.options) {
    return (
      <Select
        label={label}
        hint={hint}
        value={text}
        placeholder="Select"
        options={field.options}
        required={field.required}
        onChange={(event) => {
          onChange(event.target.value);
        }}
      />
    );
  }
  if (
    field.field_type === "text" ||
    field.field_type === "json" ||
    field.field_type === "string_list" ||
    field.field_type === "url_list"
  ) {
    const listHint =
      field.field_type === "url_list"
        ? "One http:// or https:// address on each line."
        : field.field_type === "string_list"
          ? "One entry on each line."
          : hint;
    return (
      <Textarea
        label={label}
        hint={
          field.field_type === "string_list" || field.field_type === "url_list" ? listHint : hint
        }
        value={text}
        required={field.required}
        onChange={(event) => {
          onChange(event.target.value);
        }}
      />
    );
  }
  return (
    <Input
      label={label}
      hint={hint}
      value={text}
      required={field.required}
      inputMode={
        field.field_type === "integer" || field.field_type === "number" ? "decimal" : undefined
      }
      min={field.minimum ?? undefined}
      max={field.maximum ?? undefined}
      step={field.field_type === "integer" ? 1 : field.field_type === "number" ? "any" : undefined}
      onChange={(event) => {
        onChange(event.target.value);
      }}
    />
  );
}

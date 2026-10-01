import type { ApifyConnector, ApifyField, ApifyRunWrite } from "../../types/apify";

export type FieldValue = string | boolean;

const HTTP_URL = /^https?:\/\/\S+$/i;

export function initialFieldValue(field: ApifyField): FieldValue {
  if (field.field_type === "boolean") {
    return field.default_value === true;
  }
  if (field.field_type === "string_list" || field.field_type === "url_list") {
    return listDefault(field.default_value);
  }
  if (field.default_value == null) {
    return "";
  }
  if (typeof field.default_value === "object") {
    return JSON.stringify(field.default_value, null, 2);
  }
  return String(field.default_value);
}

export function buildRunWrite(
  connector: ApifyConnector,
  values: Record<string, FieldValue>,
  maxItems: string,
  spendingCap: string,
  requestId: string,
): { payload: ApifyRunWrite } | { error: string } {
  const input: Record<string, unknown> = {};

  for (const field of connector.fields) {
    const value = values[field.key] ?? initialFieldValue(field);
    if (field.field_type === "boolean") {
      input[field.key] = value === true;
      continue;
    }
    const text = typeof value === "string" ? value.trim() : "";
    if (!text) {
      if (field.required) {
        return { error: `Enter ${field.label}.` };
      }
      continue;
    }
    if (field.field_type === "integer" || field.field_type === "number") {
      const parsed = Number(text);
      if (!Number.isFinite(parsed)) {
        return { error: `Enter a number for ${field.label}.` };
      }
      if (field.field_type === "integer" && !Number.isInteger(parsed)) {
        return { error: `Enter a whole number for ${field.label}.` };
      }
      if (field.minimum != null && parsed < field.minimum) {
        return { error: `${field.label} must be at least ${field.minimum}.` };
      }
      if (field.maximum != null && parsed > field.maximum) {
        return { error: `${field.label} must be at most ${field.maximum}.` };
      }
      input[field.key] = field.field_type === "integer" ? parsed : parsed;
      continue;
    }
    if (field.field_type === "string_list" || field.field_type === "url_list") {
      const lines = text
        .split("\n")
        .map((line) => line.trim())
        .filter(Boolean);
      if (lines.length === 0) {
        return { error: `Enter ${field.label}.` };
      }
      if (field.field_type === "url_list" && lines.some((line) => !HTTP_URL.test(line))) {
        return { error: `${field.label} must use http:// or https:// addresses.` };
      }
      input[field.key] = field.field_type === "url_list" ? lines.map((url) => ({ url })) : lines;
      continue;
    }
    if (field.field_type === "json") {
      try {
        input[field.key] = JSON.parse(text) as unknown;
      } catch {
        return { error: `${field.label} must be valid JSON.` };
      }
      continue;
    }
    input[field.key] = text;
  }

  const payload: ApifyRunWrite = { input, client_request_id: requestId };
  const items = maxItems.trim();
  if (items) {
    const parsed = Number(items);
    if (!Number.isInteger(parsed) || parsed < 1) {
      return { error: "Enter a charged result limit of at least 1." };
    }
    payload.max_items = parsed;
  }
  const cap = spendingCap.trim();
  if (cap) {
    const parsed = Number(cap);
    if (!Number.isFinite(parsed) || parsed <= 0) {
      return { error: "Enter a spending cap greater than zero." };
    }
    const minimum = connector.pricing.minimal_max_total_charge_usd;
    if (minimum != null && parsed < minimum) {
      return { error: `Enter a spending cap of at least $${minimum.toFixed(2)}.` };
    }
    payload.max_total_charge_usd = parsed;
  }
  return { payload };
}

function listDefault(value: unknown): string {
  if (!Array.isArray(value)) {
    return "";
  }
  return value
    .map((item) => {
      if (typeof item === "string") {
        return item;
      }
      if (item && typeof item === "object" && "url" in item) {
        const url = item.url;
        return typeof url === "string" ? url : "";
      }
      return "";
    })
    .filter(Boolean)
    .join("\n");
}

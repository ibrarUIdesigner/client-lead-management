export type ApifyFieldType =
  | "string"
  | "text"
  | "integer"
  | "number"
  | "boolean"
  | "string_list"
  | "url_list"
  | "enum"
  | "json"
  | "hidden";

export type ApifyFieldGroup = "search" | "limit" | "other";

export type ApifyFieldOption = {
  value: string;
  label: string;
};

export type ApifyField = {
  key: string;
  label: string;
  description: string | null;
  field_type: ApifyFieldType;
  required: boolean;
  default_value: unknown;
  options: ApifyFieldOption[] | null;
  minimum: number | null;
  maximum: number | null;
  section: string | null;
  group: ApifyFieldGroup;
};

export type ApifyPricing = {
  model: string;
  label: string;
  details: string[];
  supports_max_charge: boolean;
  supports_max_items: boolean;
  minimal_max_total_charge_usd: number | null;
};

export type ApifyConnector = {
  id: string;
  display_name: string;
  source: string;
  description: string | null;
  actor_id: string;
  last_run_at: string | null;
  last_run_status: string | null;
  has_active_run: boolean;
  pricing: ApifyPricing;
  fields: ApifyField[];
};

export type ApifyRun = {
  id: string;
  connector_id: string;
  connector_name: string;
  actor_id: string;
  apify_run_id: string;
  status: string;
  status_message: string | null;
  started_at: string;
  finished_at: string | null;
  result_count: number | null;
  usage_total_usd: number | null;
  max_items: number | null;
  max_total_charge_usd: number | null;
};

export type ApifyOverview = {
  token_configured: boolean;
  token_error: string | null;
  connectors: ApifyConnector[];
  runs: ApifyRun[];
};

export type ApifyPreviewField = {
  label: string;
  value: string;
};

export type ApifyDatasetItem = {
  item_key: string;
  title: string;
  source_url: string | null;
  detail: string | null;
  collected_at: string;
  fields: ApifyPreviewField[];
};

export type ApifyDatasetPage = {
  items: ApifyDatasetItem[];
  offset: number;
  limit: number;
  total: number;
  has_next: boolean;
};

export type ApifyRunWrite = {
  input: Record<string, unknown>;
  max_items?: number;
  max_total_charge_usd?: number;
  client_request_id: string;
};

export type ApifyImportResult = {
  created: number;
  skipped: number;
};

export const ACTIVE_RUN_STATUSES = new Set(["READY", "RUNNING", "TIMING-OUT", "ABORTING"]);

export const TERMINAL_RUN_STATUSES = new Set(["SUCCEEDED", "FAILED", "TIMED-OUT", "ABORTED"]);

export type Lead = {
  id: string;
  business_name: string;
  slug: string | null;
  industry: string | null;
  description: string | null;
  country: string | null;
  city: string | null;
  website_url: string | null;
  website_status: string | null;
  website_quality_score: number | null;
  email: string | null;
  phone: string | null;
  linkedin_url: string | null;
  instagram_url: string | null;
  facebook_url: string | null;
  google_maps_url: string | null;
  lead_score: number | null;
  lead_status: string;
  source: string | null;
  tags: string[];
  notes: string | null;
  last_contacted_at: string | null;
  next_followup_at: string | null;
  created_at: string;
  updated_at: string;
};

export type Contact = {
  id: string;
  lead_id: string;
  name: string | null;
  job_title: string | null;
  email: string | null;
  phone: string | null;
  linkedin_url: string | null;
  is_primary: boolean;
  created_at: string;
  updated_at: string;
};

export type Activity = {
  id: string;
  lead_id: string;
  type: string;
  title: string;
  description: string | null;
  details: Record<string, unknown> | null;
  created_at: string;
};

export type LeadDetail = Lead & {
  contacts: Contact[];
  activities: Activity[];
};

export type LeadPage = {
  items: Lead[];
  page: number;
  limit: number;
  total: number;
  has_next: boolean;
};

export type LeadListParams = {
  page?: number;
  limit?: number;
  q?: string;
  lead_status?: string;
  industry?: string;
  city?: string;
  country?: string;
  source?: string;
  website_status?: string;
  tag?: string;
  min_score?: number;
  sort?: string;
  direction?: "asc" | "desc";
};

export type LeadWrite = {
  business_name: string;
  industry: string | null;
  city: string | null;
  country: string | null;
  website_url: string | null;
  email: string | null;
  phone: string | null;
  source: string | null;
  tags: string[];
  notes: string | null;
  lead_status: string;
};

export type BulkLeadUpdate = {
  ids: string[];
  lead_status?: string | null;
  add_tags?: string[];
};

export type BulkLeadResult = {
  items: Lead[];
};

export type CsvPreviewRow = {
  row_number: number;
  business_name: string;
  industry: string | null;
  city: string | null;
  country: string | null;
  website_url: string | null;
  email: string | null;
  phone: string | null;
  source: string | null;
  tags: string[];
  notes: string | null;
};

export type InvalidCsvRow = {
  row_number: number;
  message: string;
};

export type LeadImportResult = {
  dry_run: boolean;
  created: number;
  valid_rows: CsvPreviewRow[];
  invalid_rows: InvalidCsvRow[];
};

export type ContactWrite = {
  name: string;
  job_title: string | null;
  email: string | null;
  phone: string | null;
  linkedin_url: string | null;
  is_primary: boolean;
};

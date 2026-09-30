export type AuditFinding = {
  code: string;
  title: string;
  detail: string;
  url?: string;
};

export type AuditReportItem = {
  code: string;
  title: string;
  detail: string;
  fix: string;
  url: string;
};

export type AuditPageCheck = {
  role: string;
  url: string;
  title: string;
};

export type AuditFieldData = {
  status: string;
  detail: string;
  lcp?: string;
  cls?: string;
  inp?: string;
};

export type OpportunityItem = {
  code: string;
  label: string;
  points: number;
};

export type AuditBrand = {
  primary_color?: string | null;
  secondary_color?: string | null;
  font_primary?: string | null;
  brand_description?: string | null;
};

export type AuditTool = {
  name: string;
  status: string;
  detail: string;
};

export type AuditAnalysis = {
  opportunity_score?: number | null;
  opportunity_breakdown?: OpportunityItem[];
  title?: string;
  final_url?: string;
  tools?: AuditTool[];
  report?: AuditReportItem[];
  pages?: AuditPageCheck[];
  field_data?: AuditFieldData | null;
  error?: string | null;
  brand?: AuditBrand;
};

export type Audit = {
  id: string;
  lead_id: string;
  url: string | null;
  status: string;
  has_desktop_screenshot: boolean;
  has_mobile_screenshot: boolean;
  performance_score: number | null;
  design_score: number | null;
  mobile_score: number | null;
  ux_score: number | null;
  seo_score: number | null;
  overall_score: number | null;
  has_ssl: boolean | null;
  is_mobile_responsive: boolean | null;
  has_clear_cta: boolean | null;
  has_contact_form: boolean | null;
  has_social_proof: boolean | null;
  has_modern_navigation: boolean | null;
  issues: AuditFinding[];
  recommendations: AuditFinding[];
  raw_analysis: AuditAnalysis | null;
  completed_at: string | null;
  created_at: string;
};

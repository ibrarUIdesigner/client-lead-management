export type ResearchSource = {
  title: string;
  url: string;
  snippet?: string | null;
  highlights?: string[] | null;
  provider: "tavily" | "exa" | string;
  score?: number | null;
  published_date?: string | null;
};

export type StructuredResearchData = {
  company_profile?: string | null;
  services_and_offerings?: string | null;
  digital_presence?: string | null;
  pain_points_and_gaps?: string[];
  competitors_and_market?: string | null;
  recent_news?: string[];
  executive_summary?: string | null;
  high_impact_opportunities?: string[];
  proactive_solutions?: string[];
  provider_used?: "tavily" | "exa" | string | null;
  fallback_used?: boolean | null;
  fallback_reason?: string | null;
};

export type LeadResearch = {
  id: string;
  lead_id: string;
  status: "PENDING" | "RUNNING" | "COMPLETED" | "FAILED" | string;
  query_used?: string | null;
  summary?: string | null;
  research_data?: StructuredResearchData | null;
  sources?: ResearchSource[] | null;
  error_message?: string | null;
  completed_at?: string | null;
  created_at: string;
  updated_at: string;
};

export type LeadResearchTrigger = {
  force_refresh?: boolean;
  custom_query?: string | null;
  preferred_tool?: "tavily" | "exa" | string;
};

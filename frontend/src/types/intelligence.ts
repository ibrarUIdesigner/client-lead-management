export type SignalItem = {
  name: string;
  type: "website" | "business" | "sales";
  source: string;
  confidence: number;
  evidence: string;
  detected_at: string;
};

export type OpportunityItem = {
  problem: string;
  evidence: string;
  source: string;
  recommended_solution: string;
  impact: "high" | "medium" | "low";
  confidence: number;
};

export type ScoreFactorItem = {
  label: string;
  points: number;
  category: string;
  reason: string;
};

export type OpportunityScoreData = {
  total_score: number;
  tier: "high" | "medium" | "low";
  tier_label: string;
  breakdown: ScoreFactorItem[];
};

export type SalesStrategyData = {
  primary_opportunity: string;
  recommended_framework: string;
  mockup_focus: string;
  outreach_angle: string;
  suggested_offer: string;
  settled_price: number;
};

export type NextActionData = {
  action: string;
  reason: string;
  confidence: number;
  cta_label: string;
  target_tab: "overview" | "audit" | "research" | "mockups" | "outreach";
  priority: "critical" | "high" | "medium" | "low";
  draft_available: boolean;
};

export type LeadIntelligence = {
  lead_id: string;
  business_name: string;
  industry: string | null;
  location: string | null;
  website_url: string | null;
  has_website: boolean;
  lead_status: string;
  opportunity_score: OpportunityScoreData;
  signals: SignalItem[];
  opportunities: OpportunityItem[];
  strategy: SalesStrategyData;
  next_action: NextActionData;
  audit_summary?: {
    id: string;
    status: string;
    overall_score?: number;
    performance_score?: number;
    mobile_score?: number;
    ux_score?: number;
    issues_count: number;
  } | null;
  research_summary?: {
    id: string;
    status: string;
    summary?: string;
    has_opportunities: boolean;
  } | null;
  mockup_status?: string | null;
  latest_mockup_id?: string | null;
  outreach_status?: string | null;
  conversation_summary?: {
    latest_direction: string;
    classification: string;
    subject: string | null;
    occurred_at: string;
    is_unread: boolean;
  } | null;
};

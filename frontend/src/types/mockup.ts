export type MockupProvider = "gemini" | "groq";
export type MockupGoal = "calls" | "whatsapp" | "bookings" | "quotes";
export type GuideMode = "keep" | "selected" | "none";

export type MockupCreateWrite = {
  lead_id: string;
  requirements?: string | null;
  source_mockup_id?: string | null;
  design_guide_id?: string | null;
  guide_mode: GuideMode;
  provider: MockupProvider;
  goal: MockupGoal;
};

export type MockupCreated = {
  id: string;
  lead_id: string;
  version: number;
  status: string;
  provider?: string | null;
  goal?: string | null;
  design_guide_id: string | null;
  design_guide_name: string | null;
  prompt?: string | null;
};

export type MockupRefineWrite = {
  instructions: string;
  provider?: MockupProvider | null;
};

export type MockupRetryWrite = {
  provider: MockupProvider;
};

export type MockupEligibility = {
  lead_id: string;
  allowed: boolean;
  reason: string;
  message: string;
  design_score: number | null;
  has_website: boolean;
  limit: number;
  scenario: "new_site" | "redesign" | null;
};

export type MockupDetail = {
  id: string;
  lead_id: string;
  business_name: string | null;
  title: string | null;
  status: string;
  version: number;
  notes: string | null;
  prompt: string | null;
  provider: string | null;
  model_name: string | null;
  goal: string | null;
  html_content: string | null;
  preview_html: string | null;
  asset_refs: Array<Record<string, unknown>> | null;
  source_mockup_id: string | null;
  screenshot_status: string | null;
  error_code: string | null;
  has_html: boolean;
  has_desktop_screenshot: boolean;
  has_mobile_screenshot: boolean;
  design_guide_id: string | null;
  design_guide_name: string | null;
  completed_at: string | null;
  created_at: string;
};

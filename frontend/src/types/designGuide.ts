export type DesignGuideSummary = {
  id: string;
  name: string;
  description: string | null;
  tags: string[];
  updated_at: string;
};

export type DesignGuide = DesignGuideSummary & {
  content: string;
  created_at: string;
};

export type DesignGuideList = {
  items: DesignGuideSummary[];
  tags: string[];
};

export type DesignGuideWrite = {
  name: string;
  description?: string | null;
  tags: string[];
  content: string;
};

export type MockupCreateWrite = {
  lead_id: string;
  requirements?: string | null;
  source_mockup_id?: string | null;
  design_guide_id?: string | null;
  guide_mode: "keep" | "selected" | "none";
  provider: "gemini" | "groq";
  goal: "calls" | "whatsapp" | "bookings" | "quotes";
};

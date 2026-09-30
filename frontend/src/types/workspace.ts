export type MockupItem = {
  id: string;
  lead_id: string;
  business_name: string;
  city: string | null;
  title: string | null;
  status: string;
  version: number;
  notes: string | null;
  prompt: string | null;
  primary_color: string | null;
  completed_at: string | null;
  created_at: string;
};

export type OutreachMessageItem = {
  id: string;
  lead_id: string;
  business_name: string;
  contact_name: string | null;
  channel: string | null;
  subject: string | null;
  message: string | null;
  status: string;
  sent_at: string | null;
  opened_at: string | null;
  replied_at: string | null;
  created_at: string;
};

export type OutreachTemplateItem = {
  id: string;
  name: string;
  channel: string | null;
  subject: string | null;
  body: string | null;
  template_type: string | null;
  is_active: boolean;
};

export type FollowupItem = {
  id: string;
  lead_id: string;
  business_name: string;
  city: string | null;
  scheduled_for: string;
  type: string | null;
  status: string;
  notes: string | null;
  completed_at: string | null;
};

export type StatusCount = {
  status: string;
  count: number;
};

export type LabelCount = {
  label: string;
  count: number;
};

export type AnalyticsSummary = {
  leads: number;
  audits_completed: number;
  mockups_ready: number;
  contacted: number;
  replies: number;
  meetings: number;
  proposals: number;
  wins: number;
  losses: number;
  by_status: StatusCount[];
  by_industry: LabelCount[];
  by_city: LabelCount[];
};

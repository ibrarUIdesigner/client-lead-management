import { api } from "./api";
import type { LearningOverview } from "./pipeline";

export type Activity = {
  leads_discovered: number;
  leads_rejected: number;
  leads_qualified: number;
  audits_completed: number;
  mockups_generated: number;
  emails_sent: number;
  first_emails: number;
  followups_sent: number;
  delivered_estimate: number;
  replies: number;
  positive_replies: number;
  interested: number;
  meetings: number;
  bounces: number;
  unsubscribes: number;
  clients_won: number;
};

export type SeriesPoint = {
  date: string;
  discovered: number;
  sent: number;
  followups: number;
  replies: number;
  positive: number;
  clients: number;
};

export type MarketRow = {
  label: string;
  qualified_leads: number;
  sent: number;
  reply_rate: number;
  positive_rate: number;
  positive: number;
  clients: number;
  conversion_rate: number;
  revenue: number;
  enough_data: boolean;
  score: number;
};

export type AngleRow = {
  label: string;
  sent: number;
  reply_rate: number;
  positive_rate: number;
  clients?: number;
  enough_data: boolean;
};

export type MockupGroup = {
  sent: number;
  reply_rate: number;
  positive_rate: number;
  enough_data: boolean;
};

export type Insights = {
  generated_at: string;
  timezone: string;
  today: Activity;
  last_24h: Activity;
  discovery: {
    total: number;
    no_website: number;
    with_opportunity: number;
    by_country: { label: string; count: number }[];
    by_category: { label: string; count: number }[];
    rejected_by_reason: Record<string, number>;
  };
  daily: SeriesPoint[];
  weekly: SeriesPoint[];
  monthly: SeriesPoint[];
  funnel: { leads: number; emailed: number; replied: number; positive: number; clients: number };
  rates: { reply_rate: number; positive_rate: number; conversion_rate: number };
  categories: MarketRow[];
  countries: MarketRow[];
  strategies: AngleRow[];
  variants: AngleRow[];
  mockup_effect: { with_mockup: MockupGroup; without_mockup: MockupGroup };
  promising: {
    lead_id: string;
    business_name: string;
    country: string | null;
    category: string | null;
    outcome: string;
    unread: boolean;
  }[];
  waiting: { interested: number; drafts: number; followups_due: number };
  recommendations: string[];
  offer_types: {
    label: string;
    new_site: { sent: number; positive_rate: number; enough_data: boolean };
    redesign: { sent: number; positive_rate: number; enough_data: boolean };
  }[];
  explore: { kind: string; name: string; reason: string }[];
  learning: LearningOverview;
};

export type ReportPreview = { subject: string; html: string; text: string };

export async function getInsights(days = 90): Promise<Insights> {
  return (await api.get<Insights>("/insights", { params: { days } })).data;
}

export async function previewReport(): Promise<ReportPreview> {
  return (await api.get<ReportPreview>("/automation/report/preview")).data;
}

export async function sendReportNow(): Promise<{ to: string; subject: string }> {
  return (await api.post<{ to: string; subject: string }>("/automation/report/send")).data;
}

import { api } from "./api";

export type PipelineJob = {
  id: string;
  step: string;
  status: "QUEUED" | "RUNNING" | "DONE" | "SKIPPED" | "FAILED";
  attempts: number;
  max_attempts: number;
  run_after: string;
  started_at: string | null;
  finished_at: string | null;
  last_error: string | null;
  detail: string | null;
};

export type LeadPipeline = {
  paused: boolean;
  next_step: string | null;
  jobs: PipelineJob[];
};

export type AutomationFlags = {
  auto_send_enabled: boolean;
  followups_auto_send: boolean;
  breakup_auto_send: boolean;
};

export type ReadinessItem = { key: string; label: string; ok: boolean; hint: string };

export type DiscoveryOverview = {
  enabled: boolean;
  limit: number;
  created_today: number;
  by_country: Record<string, number>;
  by_category: Record<string, number>;
  rejected_today: Record<string, number>;
  markets_total: number;
  markets_searched: number;
  markets_resting: number;
};

export type OutreachOverview = {
  daily_limit: number;
  drafted_today: number;
  slots_left: number;
  sent_today: number;
  waiting: number;
  drafts_to_review: number;
  next_up: {
    lead_id: string;
    business_name: string;
    country: string | null;
    priority: number;
    strategy: string;
    reasons: string[];
  }[];
};

export type LearningOverview = {
  enabled: boolean;
  updated_on: string | null;
  boosted: { kind: string; name: string; factor: number }[];
  reduced: { kind: string; name: string; factor: number }[];
  recent_moves: { date: string; kind: string; name: string; from: number; to: number; sent: number }[];
  min_total_sends: number;
  min_key_sends: number;
};

export type AutomationOverview = {
  learning: LearningOverview;
  discovery: DiscoveryOverview;
  outreach: OutreachOverview;
  flags: AutomationFlags;
  readiness: ReadinessItem[];
  last_tick: { at: string; summary: Record<string, unknown> } | null;
  sent_today: number;
  daily_cap: number;
  send_window: { timezone: string; start_hour: number; end_hour: number; open_now: boolean };
  pipeline: {
    enabled: boolean;
    min_score: number;
    jobs: Record<string, number>;
    budgets: Record<string, { used: number; limit: number | null }>;
  };
};

export async function getAutomation(): Promise<AutomationOverview> {
  return (await api.get<AutomationOverview>("/automation")).data;
}

export async function updateAutomationFlags(
  flags: Partial<AutomationFlags>,
): Promise<AutomationFlags> {
  return (await api.put<AutomationFlags>("/automation/flags", flags)).data;
}

export async function getLeadPipeline(leadId: string): Promise<LeadPipeline> {
  return (await api.get<LeadPipeline>(`/leads/${leadId}/pipeline`)).data;
}

export async function advanceLeadPipeline(leadId: string): Promise<LeadPipeline> {
  return (await api.post<LeadPipeline>(`/leads/${leadId}/pipeline/advance`)).data;
}

export async function pauseLeadPipeline(leadId: string): Promise<LeadPipeline> {
  return (await api.post<LeadPipeline>(`/leads/${leadId}/pipeline/pause`)).data;
}

export async function resumeLeadPipeline(leadId: string): Promise<LeadPipeline> {
  return (await api.post<LeadPipeline>(`/leads/${leadId}/pipeline/resume`)).data;
}

export async function retryPipelineJob(jobId: string): Promise<PipelineJob> {
  return (await api.post<PipelineJob>(`/pipeline/jobs/${jobId}/retry`)).data;
}

export type AutomationConfig = {
  paused: boolean;
  discovery_daily_limit: number;
  outreach_daily_limit: number;
  target_countries: string[];
  target_categories: string[];
  business_types: string[];
  min_score: number;
  followup_intervals: number[];
  followup_max_attempts: number;
  report_time: string;
  report_timezone: string;
  report_email: string;
  outreach_mode: "approval" | "automatic";
  learning_enabled: boolean;
  pinned_categories: string[];
  pinned_countries: string[];
  excluded_countries: string[];
};

export type Exclusion = {
  id: string;
  kind: "domain" | "email" | "name" | "category";
  value: string;
  note: string | null;
  created_at: string;
};

export type AutomationRun = {
  id: string;
  kind: string;
  status: "RUNNING" | "OK" | "FAILED" | "SKIPPED";
  started_at: string;
  finished_at: string | null;
  summary: Record<string, unknown> | null;
  error: string | null;
};

export type FailedJob = {
  id: string;
  lead_id: string;
  business_name: string | null;
  step: string;
  attempts: number;
  last_error: string | null;
  finished_at: string | null;
};

export type ActivityLog = { runs: AutomationRun[]; failed_jobs: FailedJob[] };

export type QueueItem = {
  id: string;
  lead_id: string;
  business_name: string;
  industry: string | null;
  country: string | null;
  email: string | null;
  lead_score: number | null;
  subject: string | null;
  body: string | null;
  mockup_url: string | null;
  country_policy: "allow" | "manual" | "block";
  priority: number;
  strategy: string | null;
  strategy_label: string | null;
  reasons: string[];
  variant: string | null;
  problems: string[];
  blocked: string | null;
  created_at: string;
};

export async function getAutomationConfig(): Promise<AutomationConfig> {
  return (await api.get<AutomationConfig>("/automation/config")).data;
}

export async function saveAutomationConfig(config: AutomationConfig): Promise<AutomationConfig> {
  return (await api.put<AutomationConfig>("/automation/config", config)).data;
}

export async function pauseAutomation(): Promise<AutomationConfig> {
  return (await api.post<AutomationConfig>("/automation/pause")).data;
}

export async function resumeAutomation(): Promise<AutomationConfig> {
  return (await api.post<AutomationConfig>("/automation/resume")).data;
}

export async function listExclusions(): Promise<Exclusion[]> {
  return (await api.get<Exclusion[]>("/automation/exclusions")).data;
}

export async function addExclusion(input: {
  kind: Exclusion["kind"];
  value: string;
  note?: string;
}): Promise<Exclusion> {
  return (await api.post<Exclusion>("/automation/exclusions", input)).data;
}

export async function removeExclusion(id: string): Promise<void> {
  await api.delete(`/automation/exclusions/${id}`);
}

export async function getActivityLog(): Promise<ActivityLog> {
  return (await api.get<ActivityLog>("/automation/log")).data;
}

export async function listApprovalQueue(): Promise<QueueItem[]> {
  return (await api.get<QueueItem[]>("/outreach/queue")).data;
}

export async function approveDraft(
  id: string,
  edits: { subject?: string; body?: string },
): Promise<void> {
  await api.post(`/outreach/queue/${id}/approve`, edits);
}

export async function skipDraft(id: string): Promise<void> {
  await api.post(`/outreach/queue/${id}/skip`);
}

import { api } from "./api";
import type {
  AnalyticsSummary,
  FollowupItem,
  MockupItem,
  OutreachMessageItem,
  OutreachTemplateItem,
} from "../types/workspace";

export async function listMockups(leadId?: string): Promise<MockupItem[]> {
  const response = await api.get<MockupItem[]>("/mockups", {
    params: leadId ? { lead_id: leadId } : undefined,
  });
  return response.data;
}

export async function listOutreachMessages(leadId?: string): Promise<OutreachMessageItem[]> {
  const response = await api.get<OutreachMessageItem[]>("/outreach/messages", {
    params: leadId ? { lead_id: leadId } : undefined,
  });
  return response.data;
}

export async function listOutreachTemplates(): Promise<OutreachTemplateItem[]> {
  const response = await api.get<OutreachTemplateItem[]>("/outreach/templates");
  return response.data;
}

export async function listFollowups(): Promise<FollowupItem[]> {
  const response = await api.get<FollowupItem[]>("/followups");
  return response.data;
}

export async function getAnalytics(): Promise<AnalyticsSummary> {
  const response = await api.get<AnalyticsSummary>("/analytics");
  return response.data;
}

import { api } from "./api";
import type { LeadIntelligence } from "../types/intelligence";

export async function getLeadIntelligence(leadId: string): Promise<LeadIntelligence> {
  const response = await api.get<LeadIntelligence>(`/leads/${leadId}/intelligence`);
  return response.data;
}

export async function refreshLeadIntelligence(leadId: string): Promise<LeadIntelligence> {
  const response = await api.post<LeadIntelligence>(`/leads/${leadId}/intelligence/refresh`);
  return response.data;
}

export async function listSalesPlaybooks(): Promise<string[]> {
  const response = await api.get<{ playbooks: string[] }>("/sales/playbooks");
  return response.data.playbooks;
}

export async function getSalesPlaybook(name: string): Promise<{ name: string; content: string }> {
  const response = await api.get<{ name: string; content: string }>(`/sales/playbooks/${name}`);
  return response.data;
}

export type ReplySuggestion = {
  intent: string;
  sentiment: string;
  confidence: number;
  summary: string;
  suggested_stage: string;
  recommended_action: string;
  suggested_response_subject?: string;
  suggested_response_body?: string;
};

export async function getReplySuggestion(leadId: string): Promise<ReplySuggestion> {
  const response = await api.get<ReplySuggestion>(`/leads/${leadId}/reply-suggestion`);
  return response.data;
}

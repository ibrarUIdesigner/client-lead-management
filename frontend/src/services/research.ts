import { api } from "./api";
import type { LeadResearch, LeadResearchTrigger } from "../types/research";

export async function getLeadResearch(leadId: string): Promise<LeadResearch | null> {
  try {
    const response = await api.get<LeadResearch>(`/leads/${leadId}/research`);
    return response.data;
  } catch (error: any) {
    if (error?.response?.status === 404) {
      return null;
    }
    throw error;
  }
}

export async function triggerLeadResearch(
  leadId: string,
  payload: LeadResearchTrigger = {},
): Promise<LeadResearch> {
  const response = await api.post<LeadResearch>(`/leads/${leadId}/research`, payload);
  return response.data;
}

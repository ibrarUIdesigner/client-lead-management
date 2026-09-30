import { api } from "./api";
import type { OutreachMessageItem } from "../types/workspace";

export type OutreachTone = "professional" | "warm" | "direct" | "brief";

export type OutreachGenerateInput = {
  template_id?: string;
  offer?: string;
  tone?: OutreachTone;
  sender_name?: string;
  use_ai?: boolean;
};

export type OutreachUpdateInput = {
  subject?: string;
  message?: string;
};

export type OutreachOfferSuggestion = {
  offer: string;
  source: "ai" | "audit" | "default";
};

export async function generateOutreach(
  leadId: string,
  payload: OutreachGenerateInput,
): Promise<OutreachMessageItem> {
  const response = await api.post<OutreachMessageItem>(
    `/leads/${leadId}/outreach/generate`,
    payload,
  );
  return response.data;
}

export async function suggestOutreachOffer(leadId: string): Promise<OutreachOfferSuggestion> {
  const response = await api.get<OutreachOfferSuggestion>(`/leads/${leadId}/outreach/offer`);
  return response.data;
}

export async function updateOutreach(
  messageId: string,
  payload: OutreachUpdateInput,
): Promise<OutreachMessageItem> {
  const response = await api.patch<OutreachMessageItem>(`/outreach/${messageId}`, payload);
  return response.data;
}

export async function markOutreachContacted(messageId: string): Promise<OutreachMessageItem> {
  const response = await api.post<OutreachMessageItem>(`/outreach/${messageId}/mark-contacted`);
  return response.data;
}

export async function markOutreachReplied(messageId: string): Promise<OutreachMessageItem> {
  const response = await api.post<OutreachMessageItem>(`/outreach/${messageId}/mark-replied`);
  return response.data;
}

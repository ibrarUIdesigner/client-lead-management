import { api } from "./api";
import type { OutreachMessageItem } from "../types/workspace";

export type OutreachGenerateInput = {
  template_id?: string;
};

export type OutreachUpdateInput = {
  subject?: string;
  message?: string;
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

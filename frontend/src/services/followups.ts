import { api } from "./api";
import type { FollowupItem } from "../types/workspace";

export type FollowupWrite = {
  lead_id: string;
  outreach_id?: string;
  scheduled_for: string;
  type?: string;
  notes?: string;
};

export type FollowupUpdate = {
  scheduled_for?: string;
  notes?: string;
};

export async function createFollowup(payload: FollowupWrite): Promise<FollowupItem> {
  const response = await api.post<FollowupItem>("/followups", payload);
  return response.data;
}

export async function updateFollowup(
  followupId: string,
  payload: FollowupUpdate,
): Promise<FollowupItem> {
  const response = await api.patch<FollowupItem>(`/followups/${followupId}`, payload);
  return response.data;
}

export async function completeFollowup(followupId: string): Promise<FollowupItem> {
  const response = await api.post<FollowupItem>(`/followups/${followupId}/complete`);
  return response.data;
}

export async function cancelFollowup(followupId: string): Promise<void> {
  await api.delete(`/followups/${followupId}`);
}

import { api } from "./api";
import { env } from "../lib/env";
import type { Audit } from "../types/audit";

export async function getLatestAudit(leadId: string): Promise<Audit> {
  const response = await api.get<Audit>(`/leads/${leadId}/audit`);
  return response.data;
}

export async function startAudit(leadId: string): Promise<Audit> {
  const response = await api.post<Audit>(`/leads/${leadId}/audit`);
  return response.data;
}

export async function rerunAudit(auditId: string): Promise<Audit> {
  const response = await api.post<Audit>(`/audits/${auditId}/rerun`);
  return response.data;
}

export function screenshotUrl(auditId: string, variant: "desktop" | "mobile"): string {
  return `${env.apiBaseUrl}/audits/${auditId}/screenshots/${variant}`;
}

import { api } from "./api";
import type {
  BulkLeadResult,
  BulkLeadUpdate,
  Lead,
  LeadDetail,
  LeadImportResult,
  LeadListParams,
  LeadPage,
  LeadWrite,
} from "../types/lead";

function definedParams(params: LeadListParams): Record<string, string | number> {
  const query: Record<string, string | number> = {};
  for (const [key, value] of Object.entries(params)) {
    if (value !== undefined && value !== "") {
      query[key] = value;
    }
  }
  return query;
}

export async function listLeads(params: LeadListParams): Promise<LeadPage> {
  const response = await api.get<LeadPage>("/leads", { params: definedParams(params) });
  return response.data;
}

export async function getLead(id: string): Promise<LeadDetail> {
  const response = await api.get<LeadDetail>(`/leads/${id}`);
  return response.data;
}

export async function createLead(payload: LeadWrite): Promise<Lead> {
  const response = await api.post<Lead>("/leads", payload);
  return response.data;
}

export async function updateLead(id: string, payload: LeadWrite): Promise<Lead> {
  const response = await api.patch<Lead>(`/leads/${id}`, payload);
  return response.data;
}

export async function updateLeadStatus(id: string, leadStatus: string): Promise<Lead> {
  const response = await api.patch<Lead>(`/leads/${id}/status`, { lead_status: leadStatus });
  return response.data;
}

export async function deleteLead(id: string): Promise<void> {
  await api.delete(`/leads/${id}`);
}

export async function bulkUpdateLeads(payload: BulkLeadUpdate): Promise<BulkLeadResult> {
  const response = await api.patch<BulkLeadResult>("/leads/bulk", payload);
  return response.data;
}

export async function importLeads(file: File, dryRun: boolean): Promise<LeadImportResult> {
  const body = new FormData();
  body.append("file", file);
  const response = await api.post<LeadImportResult>("/leads/import", body, {
    params: { dry_run: dryRun },
  });
  return response.data;
}

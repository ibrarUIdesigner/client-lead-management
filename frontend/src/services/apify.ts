import type {
  ApifyConnector,
  ApifyDatasetPage,
  ApifyImportResult,
  ApifyOverview,
  ApifyRun,
  ApifyRunWrite,
} from "../types/apify";
import { api } from "./api";

export async function getApify(): Promise<ApifyOverview> {
  const response = await api.get<ApifyOverview>("/apify");
  return response.data;
}

export async function createApifyConnector(payload: {
  display_name: string;
  actor_id: string;
}): Promise<ApifyConnector> {
  const response = await api.post<ApifyConnector>("/apify/connectors", payload);
  return response.data;
}

export async function deleteApifyConnector(connectorId: string): Promise<void> {
  await api.delete(`/apify/connectors/${connectorId}`);
}

export async function startApifyRun(
  connectorId: string,
  payload: ApifyRunWrite,
): Promise<ApifyRun> {
  const response = await api.post<ApifyRun>(`/apify/connectors/${connectorId}/runs`, payload);
  return response.data;
}

export async function abortApifyRun(runId: string): Promise<ApifyRun> {
  const response = await api.post<ApifyRun>(`/apify/runs/${runId}/abort`);
  return response.data;
}

export async function getApifyItems(
  runId: string,
  offset: number,
  limit: number,
): Promise<ApifyDatasetPage> {
  const response = await api.get<ApifyDatasetPage>(`/apify/runs/${runId}/items`, {
    params: { offset, limit },
  });
  return response.data;
}

export async function importApifyItems(
  runId: string,
  itemKeys: string[],
): Promise<ApifyImportResult> {
  const response = await api.post<ApifyImportResult>(`/apify/runs/${runId}/import`, {
    item_keys: itemKeys,
  });
  return response.data;
}

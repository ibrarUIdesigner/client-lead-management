import { api } from "./api";
import type { IntegrationsResponse } from "../types/integration";

export async function fetchIntegrations(): Promise<IntegrationsResponse> {
  const response = await api.get<IntegrationsResponse>("/integrations");
  return response.data;
}

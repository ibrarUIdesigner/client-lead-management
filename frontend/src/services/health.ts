import { api } from "./api";
import type { HealthResponse, ProvidersResponse } from "../types/health";

export async function fetchHealth(): Promise<HealthResponse> {
  const response = await api.get<HealthResponse>("/health");
  return response.data;
}

export async function fetchProviders(): Promise<ProvidersResponse> {
  const response = await api.get<ProvidersResponse>("/providers");
  return response.data;
}

import { api } from "./api";
import type { DiscoverySearch, DiscoverySearchWrite, DiscoveryStatus } from "../types/discovery";

export async function getDiscovery(): Promise<DiscoveryStatus> {
  const response = await api.get<DiscoveryStatus>("/discovery");
  return response.data;
}

export async function createDiscoverySearch(
  payload: DiscoverySearchWrite,
): Promise<DiscoverySearch> {
  const response = await api.post<DiscoverySearch>("/discovery/searches", payload);
  return response.data;
}

export async function updateDiscoverySearch(
  id: string,
  payload: {
    is_active?: boolean;
    use_openstreetmap?: boolean;
    use_google?: boolean;
    use_yelp?: boolean;
    use_yell?: boolean;
    use_businesslist?: boolean;
    use_epages?: boolean;
  },
): Promise<DiscoverySearch> {
  const response = await api.patch<DiscoverySearch>(`/discovery/searches/${id}`, payload);
  return response.data;
}

export async function deleteDiscoverySearch(id: string): Promise<void> {
  await api.delete(`/discovery/searches/${id}`);
}

export async function runDiscovery(searchId?: string): Promise<void> {
  await api.post("/discovery/run", null, {
    params: searchId ? { search_id: searchId } : undefined,
  });
}

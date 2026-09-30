import { useQuery } from "@tanstack/react-query";

import { fetchHealth, fetchProviders } from "../services/health";

export function useHealth() {
  return useQuery({
    queryKey: ["health"],
    queryFn: fetchHealth,
    retry: false,
  });
}

export function useProviders() {
  return useQuery({
    queryKey: ["providers"],
    queryFn: fetchProviders,
    retry: false,
    staleTime: 5 * 60 * 1000,
  });
}

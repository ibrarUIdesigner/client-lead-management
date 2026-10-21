import { useQuery } from "@tanstack/react-query";

import { fetchIntegrations } from "../services/integrations";

export function useIntegrations() {
  return useQuery({
    queryKey: ["integrations"],
    queryFn: fetchIntegrations,
    retry: false,
    staleTime: 60 * 1000,
  });
}

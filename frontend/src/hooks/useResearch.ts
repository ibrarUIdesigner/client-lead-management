import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { getLeadResearch, triggerLeadResearch } from "../services/research";
import type { LeadResearchTrigger } from "../types/research";

export function useLeadResearch(leadId: string) {
  return useQuery({
    queryKey: ["leads", leadId, "research"],
    queryFn: () => getLeadResearch(leadId),
    refetchInterval: (query) => {
      const status = query.state.data?.status;
      if (status === "PENDING" || status === "RUNNING") {
        return 2500;
      }
      return false;
    },
  });
}

export function useTriggerResearch(leadId: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (payload?: LeadResearchTrigger) => triggerLeadResearch(leadId, payload),
    onSuccess: async (data) => {
      queryClient.setQueryData(["leads", leadId, "research"], data);
      await queryClient.invalidateQueries({ queryKey: ["leads", leadId] });
      await queryClient.invalidateQueries({ queryKey: ["outreach", leadId] });
    },
  });
}

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  getLeadIntelligence,
  getReplySuggestion,
  getSalesPlaybook,
  listSalesPlaybooks,
  refreshLeadIntelligence,
  type ReplySuggestion,
} from "../services/intelligence";
import type { LeadIntelligence } from "../types/intelligence";

export function useLeadIntelligence(leadId: string) {
  return useQuery<LeadIntelligence>({
    queryKey: ["lead-intelligence", leadId],
    queryFn: () => getLeadIntelligence(leadId),
    enabled: Boolean(leadId),
    staleTime: 60_000,
  });
}

export function useRefreshLeadIntelligence(leadId: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: () => refreshLeadIntelligence(leadId),
    onSuccess: (data) => {
      queryClient.setQueryData(["lead-intelligence", leadId], data);
      void queryClient.invalidateQueries({ queryKey: ["leads", leadId] });
      void queryClient.invalidateQueries({ queryKey: ["leads"] });
    },
  });
}

export function useSalesPlaybooks() {
  return useQuery<string[]>({
    queryKey: ["sales-playbooks"],
    queryFn: listSalesPlaybooks,
    staleTime: 5 * 60_000,
  });
}

export function useSalesPlaybook(name: string | null) {
  return useQuery<{ name: string; content: string }>({
    queryKey: ["sales-playbook", name],
    queryFn: () => getSalesPlaybook(name!),
    enabled: Boolean(name),
    staleTime: 5 * 60_000,
  });
}

export function useReplySuggestion(leadId: string, enabled = true) {
  return useQuery<ReplySuggestion>({
    queryKey: ["reply-suggestion", leadId],
    queryFn: () => getReplySuggestion(leadId),
    enabled: Boolean(leadId) && enabled,
    staleTime: 60_000,
    retry: false,
  });
}

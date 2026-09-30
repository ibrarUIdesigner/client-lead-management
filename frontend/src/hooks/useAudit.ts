import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { apiErrorCode } from "../lib/apiError";
import { getLatestAudit, rerunAudit, startAudit } from "../services/audits";

export function useLatestAudit(leadId: string) {
  return useQuery({
    queryKey: ["leads", leadId, "audit"],
    queryFn: () => getLatestAudit(leadId),
    retry: (failureCount, error) => apiErrorCode(error) !== "AUDIT_NOT_FOUND" && failureCount < 1,
    refetchInterval: (query) => {
      const status = query.state.data?.status;
      if (status === "PENDING" || status === "RUNNING") {
        return 2000;
      }
      return false;
    },
  });
}

export function useStartAudit(leadId: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: () => startAudit(leadId),
    onSuccess: async (audit) => {
      queryClient.setQueryData(["leads", leadId, "audit"], audit);
      await queryClient.invalidateQueries({ queryKey: ["leads", leadId] });
    },
  });
}

export function useRerunAudit(leadId: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (auditId: string) => rerunAudit(auditId),
    onSuccess: async (audit) => {
      queryClient.setQueryData(["leads", leadId, "audit"], audit);
      await queryClient.invalidateQueries({ queryKey: ["leads", leadId] });
    },
  });
}

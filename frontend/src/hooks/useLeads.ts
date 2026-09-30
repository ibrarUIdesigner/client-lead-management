import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import {
  bulkUpdateLeads,
  createLead,
  deleteLead,
  getLead,
  importLeads,
  listLeads,
  updateLead,
  updateLeadStatus,
} from "../services/leads";
import type { BulkLeadUpdate, LeadListParams, LeadWrite } from "../types/lead";

export function useLeads(params: LeadListParams) {
  return useQuery({
    queryKey: ["leads", params],
    queryFn: () => listLeads(params),
  });
}

export function useLead(id: string | undefined) {
  return useQuery({
    queryKey: ["leads", id],
    queryFn: () => getLead(id ?? ""),
    enabled: Boolean(id),
  });
}

export function useCreateLead() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (payload: LeadWrite) => createLead(payload),
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: ["leads"] });
    },
  });
}

export function useUpdateLead(id: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (payload: LeadWrite) => updateLead(id, payload),
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: ["leads"] });
    },
  });
}

export function useDeleteLead() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (id: string) => deleteLead(id),
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: ["leads"] });
    },
  });
}

export function useUpdateLeadStatus() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ id, leadStatus }: { id: string; leadStatus: string }) =>
      updateLeadStatus(id, leadStatus),
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: ["leads"] });
    },
  });
}

export function useBulkUpdateLeads() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (payload: BulkLeadUpdate) => bulkUpdateLeads(payload),
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: ["leads"] });
    },
  });
}

export function useImportLeads() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ file, dryRun }: { file: File; dryRun: boolean }) => importLeads(file, dryRun),
    onSuccess: async (_result, variables) => {
      if (!variables.dryRun) {
        await queryClient.invalidateQueries({ queryKey: ["leads"] });
      }
    },
  });
}

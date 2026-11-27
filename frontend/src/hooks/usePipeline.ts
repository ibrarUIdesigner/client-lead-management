import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import {
  addExclusion,
  advanceLeadPipeline,
  approveDraft,
  getActivityLog,
  getAutomation,
  getAutomationConfig,
  getLeadPipeline,
  listApprovalQueue,
  listExclusions,
  pauseAutomation,
  pauseLeadPipeline,
  removeExclusion,
  resumeAutomation,
  resumeLeadPipeline,
  retryPipelineJob,
  saveAutomationConfig,
  skipDraft,
  updateAutomationFlags,
  type AutomationFlags,
} from "../services/pipeline";

export function useAutomation() {
  return useQuery({
    queryKey: ["automation"],
    queryFn: getAutomation,
    refetchInterval: 30_000,
  });
}

export function useUpdateAutomationFlags() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (flags: Partial<AutomationFlags>) => updateAutomationFlags(flags),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["automation"] }),
  });
}

export function useLeadPipeline(leadId: string) {
  return useQuery({
    queryKey: ["lead-pipeline", leadId],
    queryFn: () => getLeadPipeline(leadId),
    enabled: Boolean(leadId),
    refetchInterval: 20_000,
  });
}

export function useLeadPipelineActions(leadId: string) {
  const queryClient = useQueryClient();
  const refresh = () => queryClient.invalidateQueries({ queryKey: ["lead-pipeline", leadId] });
  return {
    advance: useMutation({ mutationFn: () => advanceLeadPipeline(leadId), onSuccess: refresh }),
    pause: useMutation({ mutationFn: () => pauseLeadPipeline(leadId), onSuccess: refresh }),
    resume: useMutation({ mutationFn: () => resumeLeadPipeline(leadId), onSuccess: refresh }),
    retry: useMutation({ mutationFn: (jobId: string) => retryPipelineJob(jobId), onSuccess: refresh }),
  };
}

export function useAutomationConfig() {
  return useQuery({ queryKey: ["automation-config"], queryFn: getAutomationConfig });
}

export function useAutomationConfigActions() {
  const queryClient = useQueryClient();
  const refresh = () => {
    void queryClient.invalidateQueries({ queryKey: ["automation-config"] });
    void queryClient.invalidateQueries({ queryKey: ["automation"] });
  };
  return {
    save: useMutation({ mutationFn: saveAutomationConfig, onSuccess: refresh }),
    pause: useMutation({ mutationFn: pauseAutomation, onSuccess: refresh }),
    resume: useMutation({ mutationFn: resumeAutomation, onSuccess: refresh }),
  };
}

export function useExclusions() {
  const queryClient = useQueryClient();
  const query = useQuery({ queryKey: ["automation-exclusions"], queryFn: listExclusions });
  const refresh = () => queryClient.invalidateQueries({ queryKey: ["automation-exclusions"] });
  return {
    query,
    add: useMutation({ mutationFn: addExclusion, onSuccess: refresh }),
    remove: useMutation({ mutationFn: removeExclusion, onSuccess: refresh }),
  };
}

export function useActivityLog() {
  return useQuery({
    queryKey: ["automation-log"],
    queryFn: getActivityLog,
    refetchInterval: 30_000,
  });
}

export function useApprovalQueue() {
  const queryClient = useQueryClient();
  const query = useQuery({ queryKey: ["approval-queue"], queryFn: listApprovalQueue });
  const refresh = () => {
    void queryClient.invalidateQueries({ queryKey: ["approval-queue"] });
    void queryClient.invalidateQueries({ queryKey: ["automation"] });
  };
  return {
    query,
    approve: useMutation({
      mutationFn: (input: { id: string; subject?: string; body?: string }) =>
        approveDraft(input.id, { subject: input.subject, body: input.body }),
      onSuccess: refresh,
    }),
    skip: useMutation({ mutationFn: skipDraft, onSuccess: refresh }),
  };
}

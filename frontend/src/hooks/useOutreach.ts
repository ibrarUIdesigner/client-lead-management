import { useMutation, useQuery, useQueryClient, type QueryClient } from "@tanstack/react-query";

import {
  generateOutreach,
  markOutreachContacted,
  markOutreachReplied,
  suggestOutreachOffer,
  updateOutreach,
  type OutreachGenerateInput,
  type OutreachUpdateInput,
} from "../services/outreach";
import {
  cancelFollowup,
  completeFollowup,
  createFollowup,
  updateFollowup,
  type FollowupUpdate,
  type FollowupWrite,
} from "../services/followups";
import type { OutreachMessageItem } from "../types/workspace";

function rememberMessage(queryClient: QueryClient, message: OutreachMessageItem) {
  queryClient.setQueriesData<OutreachMessageItem[]>({ queryKey: ["outreach"] }, (current) => {
    if (!current) {
      return current;
    }
    const index = current.findIndex((item) => item.id === message.id);
    if (index === -1) {
      return current.some((item) => item.lead_id === message.lead_id)
        ? [message, ...current]
        : current;
    }
    const next = current.slice();
    next[index] = message;
    return next;
  });
}

async function refreshWorkspace(queryClient: QueryClient) {
  await Promise.all([
    queryClient.invalidateQueries({ queryKey: ["outreach"] }),
    queryClient.invalidateQueries({ queryKey: ["followups"] }),
    queryClient.invalidateQueries({ queryKey: ["analytics"] }),
    queryClient.invalidateQueries({ queryKey: ["leads"] }),
  ]);
}

export function useSuggestOutreachOffer(leadId: string, enabled: boolean) {
  return useQuery({
    queryKey: ["outreach-offer", leadId],
    queryFn: () => suggestOutreachOffer(leadId),
    enabled: Boolean(leadId) && enabled,
    staleTime: 60_000,
  });
}

export function useGenerateOutreach(leadId: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (payload: OutreachGenerateInput) => generateOutreach(leadId, payload),
    onSuccess: async (message) => {
      rememberMessage(queryClient, message);
      await refreshWorkspace(queryClient);
    },
  });
}

export function useUpdateOutreach() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ messageId, payload }: { messageId: string; payload: OutreachUpdateInput }) =>
      updateOutreach(messageId, payload),
    onSuccess: async (message) => {
      rememberMessage(queryClient, message);
      await refreshWorkspace(queryClient);
    },
  });
}

export function useMarkContacted() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (messageId: string) => markOutreachContacted(messageId),
    onSuccess: async (message) => {
      rememberMessage(queryClient, message);
      await refreshWorkspace(queryClient);
    },
  });
}

export function useMarkReplied() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (messageId: string) => markOutreachReplied(messageId),
    onSuccess: async (message) => {
      rememberMessage(queryClient, message);
      await refreshWorkspace(queryClient);
    },
  });
}

export function useScheduleFollowup() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (payload: FollowupWrite) => createFollowup(payload),
    onSuccess: async () => {
      await refreshWorkspace(queryClient);
    },
  });
}

export function useUpdateFollowup() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ followupId, payload }: { followupId: string; payload: FollowupUpdate }) =>
      updateFollowup(followupId, payload),
    onSuccess: async () => {
      await refreshWorkspace(queryClient);
    },
  });
}

export function useCompleteFollowup() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (followupId: string) => completeFollowup(followupId),
    onSuccess: async () => {
      await refreshWorkspace(queryClient);
    },
  });
}

export function useCancelFollowup() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (followupId: string) => cancelFollowup(followupId),
    onSuccess: async () => {
      await refreshWorkspace(queryClient);
    },
  });
}

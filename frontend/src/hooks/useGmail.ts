import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import {
  disconnectGmail,
  getGmailStatus,
  listLeadEmails,
  markLeadEmailsRead,
  replyLeadEmail,
  sendLeadEmail,
  startGmailConnect,
  syncGmail,
  type ReplyLeadEmailInput,
  type SendLeadEmailInput,
} from "../services/gmail";

export function useGmailStatus() {
  return useQuery({
    queryKey: ["gmail-status"],
    queryFn: getGmailStatus,
    staleTime: 15_000,
  });
}

export function useLeadEmails(leadId: string) {
  return useQuery({
    queryKey: ["lead-emails", leadId],
    queryFn: () => listLeadEmails(leadId),
    enabled: Boolean(leadId),
    refetchInterval: 15_000,
    refetchOnWindowFocus: true,
  });
}

export function useLeadEmailSync(leadId: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: syncGmail,
    onSuccess: async () => {
      await Promise.all([
        queryClient.invalidateQueries({ queryKey: ["gmail-status"] }),
        queryClient.invalidateQueries({ queryKey: ["lead-emails", leadId] }),
        queryClient.invalidateQueries({ queryKey: ["leads", leadId] }),
        queryClient.invalidateQueries({ queryKey: ["leads"] }),
        queryClient.invalidateQueries({ queryKey: ["outreach"] }),
        queryClient.invalidateQueries({ queryKey: ["followups"] }),
      ]);
    },
  });
}

export function useConnectGmail() {
  return useMutation({
    mutationFn: startGmailConnect,
  });
}

export function useDisconnectGmail() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: disconnectGmail,
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: ["gmail-status"] });
    },
  });
}

export function useSyncGmail() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: syncGmail,
    onSuccess: async () => {
      await Promise.all([
        queryClient.invalidateQueries({ queryKey: ["gmail-status"] }),
        queryClient.invalidateQueries({ queryKey: ["lead-emails"] }),
        queryClient.invalidateQueries({ queryKey: ["leads"] }),
        queryClient.invalidateQueries({ queryKey: ["outreach"] }),
        queryClient.invalidateQueries({ queryKey: ["followups"] }),
      ]);
    },
  });
}

export function useSendLeadEmail(leadId: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (payload: SendLeadEmailInput) => sendLeadEmail(leadId, payload),
    onSuccess: async () => {
      await Promise.all([
        queryClient.invalidateQueries({ queryKey: ["lead-emails", leadId] }),
        queryClient.invalidateQueries({ queryKey: ["leads"] }),
        queryClient.invalidateQueries({ queryKey: ["outreach"] }),
      ]);
    },
  });
}

export function useReplyLeadEmail(leadId: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ emailId, payload }: { emailId: string; payload: ReplyLeadEmailInput }) =>
      replyLeadEmail(leadId, emailId, payload),
    onSuccess: async () => {
      await Promise.all([
        queryClient.invalidateQueries({ queryKey: ["lead-emails", leadId] }),
        queryClient.invalidateQueries({ queryKey: ["leads"] }),
      ]);
    },
  });
}

export function useMarkLeadEmailsRead(leadId: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: () => markLeadEmailsRead(leadId),
    onSuccess: async () => {
      await Promise.all([
        queryClient.invalidateQueries({ queryKey: ["lead-emails", leadId] }),
        queryClient.invalidateQueries({ queryKey: ["leads"] }),
      ]);
    },
  });
}

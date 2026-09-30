import { useMutation, useQueryClient } from "@tanstack/react-query";

import { createContact, deleteContact, updateContact } from "../services/contacts";
import type { ContactWrite } from "../types/lead";

export function useCreateContact(leadId: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (payload: ContactWrite) => createContact(leadId, payload),
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: ["leads", leadId] });
    },
  });
}

export function useUpdateContact(leadId: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ contactId, payload }: { contactId: string; payload: Partial<ContactWrite> }) =>
      updateContact(contactId, payload),
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: ["leads", leadId] });
    },
  });
}

export function useDeleteContact(leadId: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (contactId: string) => deleteContact(contactId),
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: ["leads", leadId] });
    },
  });
}

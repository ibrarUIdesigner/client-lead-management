import { api } from "./api";
import type { Contact, ContactWrite } from "../types/lead";

export async function createContact(leadId: string, payload: ContactWrite): Promise<Contact> {
  const response = await api.post<Contact>(`/leads/${leadId}/contacts`, payload);
  return response.data;
}

export async function updateContact(
  contactId: string,
  payload: Partial<ContactWrite>,
): Promise<Contact> {
  const response = await api.patch<Contact>(`/contacts/${contactId}`, payload);
  return response.data;
}

export async function deleteContact(contactId: string): Promise<void> {
  await api.delete(`/contacts/${contactId}`);
}

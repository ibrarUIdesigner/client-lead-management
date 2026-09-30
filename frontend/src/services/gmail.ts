import { api } from "./api";

export type GmailStatus = {
  configured: boolean;
  connected: boolean;
  email: string | null;
  status: string | null;
  last_synced_at: string | null;
  last_error: string | null;
  sync_enabled: boolean;
  needs_reauth: boolean;
};

export type LeadEmailItem = {
  id: string;
  lead_id: string | null;
  gmail_account_id: string;
  outreach_message_id: string | null;
  direction: "OUTBOUND" | "INBOUND" | string;
  classification: string;
  recipient_email: string | null;
  sender_email: string | null;
  subject: string | null;
  body_text: string | null;
  body_html: string | null;
  gmail_message_id: string;
  gmail_thread_id: string;
  rfc_message_id: string | null;
  occurred_at: string;
  is_unread: boolean;
  needs_review: boolean;
  created_at: string;
};

export type LeadEmailThread = {
  last_contacted_at: string | null;
  last_replied_at: string | null;
  next_followup_at: string | null;
  email_unread: boolean;
  do_not_contact: boolean;
  email_suppressed: boolean;
  unread_count: number;
  items: LeadEmailItem[];
};

export type SendLeadEmailInput = {
  to?: string;
  subject: string;
  body: string;
  outreach_message_id?: string;
  attachment_audit_id?: string;
  attachment_mockup_ids?: string[];
  idempotency_key?: string;
};

export type ReplyLeadEmailInput = {
  body: string;
  subject?: string;
  idempotency_key?: string;
};

export async function getGmailStatus() {
  const { data } = await api.get<GmailStatus>("/gmail/status");
  return data;
}

export async function startGmailConnect() {
  const { data } = await api.get<{ authorization_url: string }>("/gmail/oauth/start");
  return data;
}

export async function disconnectGmail() {
  const { data } = await api.post<GmailStatus>("/gmail/disconnect");
  return data;
}

export async function syncGmail() {
  const { data } = await api.post<{
    processed: number;
    matched: number;
    skipped: number;
    ambiguous: number;
    history_reset: boolean;
    account_email: string | null;
  }>("/gmail/sync");
  return data;
}

export async function listLeadEmails(leadId: string) {
  const { data } = await api.get<LeadEmailThread>(`/leads/${leadId}/emails`);
  return data;
}

export async function markLeadEmailsRead(leadId: string) {
  const { data } = await api.post<LeadEmailThread>(`/leads/${leadId}/emails/mark-read`);
  return data;
}

export async function sendLeadEmail(leadId: string, payload: SendLeadEmailInput) {
  const headers: Record<string, string> = {};
  if (payload.idempotency_key) {
    headers["Idempotency-Key"] = payload.idempotency_key;
  }
  const { data } = await api.post<LeadEmailItem>(`/leads/${leadId}/emails/send`, payload, {
    headers,
  });
  return data;
}

export async function replyLeadEmail(
  leadId: string,
  emailId: string,
  payload: ReplyLeadEmailInput,
) {
  const headers: Record<string, string> = {};
  if (payload.idempotency_key) {
    headers["Idempotency-Key"] = payload.idempotency_key;
  }
  const { data } = await api.post<LeadEmailItem>(
    `/leads/${leadId}/emails/${emailId}/reply`,
    payload,
    { headers },
  );
  return data;
}

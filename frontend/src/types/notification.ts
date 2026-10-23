export type NotificationPriority = "LOW" | "NORMAL" | "HIGH" | "URGENT";

export type NotificationType =
  | "NEW_EMAIL_REPLY"
  | "POSITIVE_REPLY"
  | "OBJECTION_REPLY"
  | "MEETING_REQUEST"
  | "FOLLOWUP_DUE"
  | "MOCKUP_READY"
  | "RESEARCH_COMPLETE"
  | "AUDIT_COMPLETE"
  | "EMAIL_DRAFT_READY"
  | "EMAIL_SEND_FAILED"
  | "LEAD_QUALIFIED"
  | "HIGH_OPPORTUNITY_LEAD"
  | "APIFY_JOB_COMPLETE";

export interface NotificationItem {
  id: string;
  user_id: string;
  type: string;
  title: string;
  message: string;
  priority: NotificationPriority;
  lead_id?: string | null;
  campaign_id?: string | null;
  email_id?: string | null;
  action_url?: string | null;
  metadata?: Record<string, any> | null;
  is_read: boolean;
  created_at: string;
  read_at?: string | null;
}

export interface NotificationListResponse {
  items: NotificationItem[];
  total: number;
  unread_count: number;
}

export interface UnreadCountResponse {
  unread_count: number;
}

export interface PushPublicKeyResponse {
  public_key: string;
  configured: boolean;
}

export interface NotificationPreferences {
  user_id: string;
  browser_push_enabled: boolean;
  preferences: Record<string, boolean>;
}

export interface NotificationPreferencesUpdate {
  browser_push_enabled?: boolean;
  preferences?: Record<string, boolean>;
}

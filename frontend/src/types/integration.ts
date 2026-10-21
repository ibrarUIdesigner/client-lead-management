export type IntegrationStatus = "active" | "ready" | "not_configured" | "public";

export interface IntegrationItem {
  id: string;
  name: string;
  category: string;
  description: string;
  status: IntegrationStatus;
  is_configured: boolean;
  env_var: string;
  details: string;
  website: string | null;
}

export interface IntegrationsResponse {
  integrations: IntegrationItem[];
  total_count: number;
  configured_count: number;
}

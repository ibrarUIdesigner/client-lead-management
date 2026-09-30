export type HealthResponse = {
  status: "ok";
  service: string;
  environment: string;
  database: "ok" | "unavailable";
  email_drafts: "gemini" | "groq" | "unconfigured";
  gemini?: "ready" | "missing";
  groq?: "ready" | "missing";
};

export type ProviderSnapshot = {
  id: "gemini" | "groq";
  configured: boolean;
  active: boolean;
  model: string;
  display_name: string | null;
  listed: boolean | null;
  input_tokens: number | null;
  output_tokens: number | null;
  prompt_usd_per_million: number | null;
  completion_usd_per_million: number | null;
  credits: string;
};

export type ProvidersResponse = {
  providers: ProviderSnapshot[];
};

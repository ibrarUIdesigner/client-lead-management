export type HealthResponse = {
  status: "ok";
  service: string;
  environment: string;
  database: "ok" | "unavailable";
  email_drafts: "gemini" | "groq" | "unconfigured";
  gemini?: "ready" | "missing";
  groq?: "ready" | "missing";
};

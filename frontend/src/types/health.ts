export type HealthResponse = {
  status: "ok";
  service: string;
  environment: string;
  database: "ok" | "unavailable";
};

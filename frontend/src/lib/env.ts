const apiBaseUrl =
  import.meta.env.VITE_API_BASE_URL ??
  (import.meta.env.PROD ? "/api/v1" : "http://localhost:8000/api/v1");

export const env = {
  apiBaseUrl,
};

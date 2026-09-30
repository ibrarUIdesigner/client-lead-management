export type ApiErrorBody = {
  error: {
    code: string;
    message: string;
    details: Record<string, unknown>;
  };
};

export function isApiErrorBody(value: unknown): value is ApiErrorBody {
  if (typeof value !== "object" || value === null || !("error" in value)) {
    return false;
  }

  const error = value.error;
  if (typeof error !== "object" || error === null || !("message" in error)) {
    return false;
  }

  return typeof error.message === "string";
}

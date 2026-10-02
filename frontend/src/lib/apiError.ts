import axios from "axios";

import { isApiErrorBody } from "../types/api";

export function apiErrorMessage(error: unknown, fallback: string): string {
  if (axios.isAxiosError(error) && isApiErrorBody(error.response?.data)) {
    return error.response.data.error.message;
  }

  return fallback;
}

export function isOfflineError(error: unknown): boolean {
  if (typeof navigator !== "undefined" && navigator.onLine === false) {
    return true;
  }

  return axios.isAxiosError(error) && error.response == null && error.code !== "ECONNABORTED";
}

export function apiErrorCode(error: unknown): string | null {
  if (axios.isAxiosError(error) && isApiErrorBody(error.response?.data)) {
    return error.response.data.error.code;
  }

  return null;
}

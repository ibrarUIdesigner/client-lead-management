import { api } from "../services/api";

const SESSION_KEY = "clm.session";
const TOKEN_KEY = "clm.token";
const EMAIL_KEY = "clm.email";

const STATIC_EMAIL = "ibrarUIdesigner@gmail.com";
const STATIC_PASSWORD = "CAquiByIbrar@1234";

export const DEMO_CREDENTIALS = {
  email: STATIC_EMAIL,
  password: STATIC_PASSWORD,
};

export function isAuthenticated(): boolean {
  return sessionStorage.getItem(SESSION_KEY) === "1" && Boolean(sessionStorage.getItem(TOKEN_KEY));
}

export async function signIn(email: string, password: string): Promise<boolean> {
  try {
    const response = await api.post<{ access_token: string; email: string }>("/auth/login", {
      email: email.trim(),
      password,
    });
    sessionStorage.setItem(SESSION_KEY, "1");
    sessionStorage.setItem(TOKEN_KEY, response.data.access_token);
    sessionStorage.setItem(EMAIL_KEY, response.data.email);
    return true;
  } catch {
    return false;
  }
}

export function signOut(): void {
  sessionStorage.removeItem(SESSION_KEY);
  sessionStorage.removeItem(TOKEN_KEY);
  sessionStorage.removeItem(EMAIL_KEY);
}

export function sessionEmail(): string {
  return sessionStorage.getItem(EMAIL_KEY) || STATIC_EMAIL;
}


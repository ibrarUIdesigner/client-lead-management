const SESSION_KEY = "clm.session";

const STATIC_EMAIL = "ibrarUIdesigner@gmail.com";
const STATIC_PASSWORD = "CAquiByIbrar@1234";

export function isAuthenticated(): boolean {
  return sessionStorage.getItem(SESSION_KEY) === "1";
}

export function signIn(email: string, password: string): boolean {
  const matches =
    email.trim().toLowerCase() === STATIC_EMAIL.toLowerCase() && password === STATIC_PASSWORD;

  if (!matches) {
    return false;
  }

  sessionStorage.setItem(SESSION_KEY, "1");
  return true;
}

export function signOut(): void {
  sessionStorage.removeItem(SESSION_KEY);
}

export function sessionEmail(): string {
  return STATIC_EMAIL;
}

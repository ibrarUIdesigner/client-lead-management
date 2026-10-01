import { type FormEvent, useState } from "react";
import { Navigate, useNavigate } from "react-router-dom";

import { Button } from "../components/ui/Button";
import { Input } from "../components/ui/Input";
import { isAuthenticated, signIn } from "../lib/auth";

export function LoginPage() {
  const navigate = useNavigate();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);

  if (isAuthenticated()) {
    return <Navigate to="/" replace />;
  }

  function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();

    if (signIn(email, password)) {
      navigate("/", { replace: true });
      return;
    }

    setError("That email or password doesn't match.");
  }

  return (
    <div className="grid min-h-screen lg:grid-cols-[minmax(0,0.9fr)_minmax(420px,1fr)]">
      <aside className="hidden flex-col justify-between bg-ink px-12 py-10 text-white lg:flex">
        <p className="text-h4 font-semibold tracking-tight">Client Acquisition</p>
        <div className="max-w-md">
          <p className="text-display-lg font-semibold tracking-tight">Sign in to the workspace.</p>
          <p className="mt-4 max-w-sm text-body-lg text-white/70">
            Leads, outreach, and follow-ups stay behind this door.
          </p>
        </div>
        <p className="text-caption text-white/50">Private workspace</p>
      </aside>

      <main className="flex items-center justify-center bg-background px-4 py-10">
        <div className="w-full max-w-[400px]">
          <p className="text-h4 font-semibold text-ink lg:hidden">Client Acquisition</p>
          <h1 className="mt-8 text-h1 font-semibold tracking-tight text-ink lg:mt-0">Sign in</h1>
          <p className="mt-2 text-body text-gray-600">Use your workspace email and password.</p>

          <form className="mt-8 flex flex-col gap-5" onSubmit={handleSubmit}>
            <Input
              label="Email"
              type="email"
              name="email"
              autoComplete="username"
              autoFocus
              required
              value={email}
              onChange={(event) => {
                setEmail(event.target.value);
                setError(null);
              }}
            />
            <Input
              label="Password"
              type="password"
              name="password"
              autoComplete="current-password"
              required
              value={password}
              onChange={(event) => {
                setPassword(event.target.value);
                setError(null);
              }}
            />

            {error ? (
              <p className="text-small text-danger" role="alert">
                {error}
              </p>
            ) : null}

            <Button type="submit" className="mt-1 w-full">
              Sign in
            </Button>
          </form>
        </div>
      </main>
    </div>
  );
}

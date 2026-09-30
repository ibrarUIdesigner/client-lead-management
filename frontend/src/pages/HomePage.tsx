import axios from "axios";
import { RefreshCw } from "lucide-react";

import { useHealth } from "../hooks/useHealth";
import { isApiErrorBody } from "../types/api";

function errorMessage(error: unknown): string {
  if (axios.isAxiosError(error) && isApiErrorBody(error.response?.data)) {
    return error.response.data.error.message;
  }

  return "The API could not be reached.";
}

export function HomePage() {
  const health = useHealth();

  return (
    <main className="mx-auto flex min-h-screen w-full max-w-3xl flex-col justify-center px-6 py-16">
      <p className="text-sm font-medium text-primary">Client Acquisition Tool</p>
      <h1 className="mt-3 text-3xl font-bold tracking-tight text-ink">Foundation</h1>
      <p className="mt-3 max-w-xl text-base leading-6 text-slate-600">
        The API, routing, and database connection are wired. Lead management starts in the next
        phase.
      </p>

      <section className="mt-10 rounded-xl border border-slate-200 bg-white p-6">
        <div className="flex items-center justify-between gap-4">
          <h2 className="text-base font-semibold text-ink">API status</h2>
          <button
            type="button"
            onClick={() => {
              void health.refetch();
            }}
            className="inline-flex h-10 items-center gap-2 rounded-lg border border-slate-300 px-4 text-sm font-semibold text-slate-700 hover:bg-slate-100"
          >
            <RefreshCw size={16} aria-hidden="true" />
            Retry
          </button>
        </div>

        {health.isPending ? <p className="mt-6 text-sm text-slate-600">Checking the API…</p> : null}

        {health.isError ? (
          <p className="mt-6 text-sm text-red-600" role="alert">
            {errorMessage(health.error)}
          </p>
        ) : null}

        {health.data ? (
          <dl className="mt-6 grid gap-4 sm:grid-cols-3">
            <div>
              <dt className="text-xs font-medium text-slate-500">Service</dt>
              <dd className="mt-1 text-sm text-ink">{health.data.service}</dd>
            </div>
            <div>
              <dt className="text-xs font-medium text-slate-500">Environment</dt>
              <dd className="mt-1 text-sm text-ink">{health.data.environment}</dd>
            </div>
            <div>
              <dt className="text-xs font-medium text-slate-500">Database</dt>
              <dd className="mt-1 text-sm text-ink">
                {health.data.database === "ok" ? "Connected" : "Unavailable"}
              </dd>
            </div>
          </dl>
        ) : null}
      </section>
    </main>
  );
}

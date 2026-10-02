import type { ReactNode } from "react";

import { useOnline } from "../../hooks/useOnline";
import { apiErrorMessage, isOfflineError } from "../../lib/apiError";
import { Button } from "../ui/Button";
import { LoadingState } from "./LoadingState";
import { OfflineState } from "./OfflineState";

type QueryGateProps = {
  pending: boolean;
  error: unknown;
  onRetry: () => void;
  fallback: string;
  loadingLabel?: string;
  children: ReactNode;
};

export function QueryGate({
  pending,
  error,
  onRetry,
  fallback,
  loadingLabel = "Loading",
  children,
}: QueryGateProps) {
  const online = useOnline();

  if (!online || (error && isOfflineError(error))) {
    return <OfflineState onRetry={onRetry} />;
  }

  if (pending) {
    return <LoadingState label={loadingLabel} />;
  }

  if (error) {
    return (
      <div className="flex flex-col items-start gap-3 rounded-card border border-red-200 bg-red-50 px-4 py-6 sm:px-6" role="alert">
        <h2 className="text-h4 font-semibold text-ink">Could not load this</h2>
        <p className="max-w-lg text-body text-red-800">{apiErrorMessage(error, fallback)}</p>
        <Button variant="secondary" onClick={onRetry}>
          Try again
        </Button>
      </div>
    );
  }

  return children;
}

import type { ReactNode } from "react";

import { apiErrorMessage } from "../../lib/apiError";
import { Button } from "../ui/Button";
import { Skeleton } from "../ui/Skeleton";

type QueryGateProps = {
  pending: boolean;
  error: unknown;
  onRetry: () => void;
  fallback: string;
  children: ReactNode;
};

export function QueryGate({ pending, error, onRetry, fallback, children }: QueryGateProps) {
  if (pending) {
    return (
      <div className="space-y-3" aria-busy="true">
        <Skeleton className="h-8 w-40" />
        <Skeleton className="h-40 w-full" />
      </div>
    );
  }

  if (error) {
    return (
      <div className="flex flex-col items-start gap-3" role="alert">
        <p className="text-body text-danger">{apiErrorMessage(error, fallback)}</p>
        <Button variant="secondary" onClick={onRetry}>
          Retry
        </Button>
      </div>
    );
  }

  return children;
}

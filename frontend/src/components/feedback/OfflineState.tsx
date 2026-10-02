import { WifiOff } from "lucide-react";

import { Button } from "../ui/Button";

type OfflineStateProps = {
  onRetry?: () => void;
  title?: string;
  description?: string;
};

export function OfflineState({
  onRetry,
  title = "You are offline",
  description = "Reconnect, then try again. This page needs the server to load.",
}: OfflineStateProps) {
  return (
    <div
      className="flex flex-col items-start gap-3 rounded-card border border-dashed border-amber-300 bg-amber-50 px-4 py-8 sm:px-6 sm:py-10"
      role="alert"
    >
      <span className="inline-flex size-10 items-center justify-center rounded-full bg-white text-amber-700">
        <WifiOff className="size-5" aria-hidden="true" />
      </span>
      <h2 className="text-h3 font-semibold text-ink">{title}</h2>
      <p className="max-w-lg text-body text-amber-950">{description}</p>
      {onRetry ? (
        <Button variant="secondary" onClick={onRetry}>
          Try again
        </Button>
      ) : null}
    </div>
  );
}

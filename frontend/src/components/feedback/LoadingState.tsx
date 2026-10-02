import { Skeleton } from "../ui/Skeleton";
import { cn } from "../../lib/cn";

type LoadingStateProps = {
  label?: string;
  framed?: boolean;
};

export function LoadingState({ label = "Loading", framed = true }: LoadingStateProps) {
  return (
    <div
      className={cn("space-y-3", framed && "rounded-card border border-gray-200 bg-white p-4 sm:p-6")}
      aria-busy="true"
      aria-live="polite"
    >
      <p className="text-small font-medium text-gray-500">{label}</p>
      <Skeleton className="h-4 w-1/3" />
      <Skeleton className="h-12 w-full" />
      <Skeleton className="h-12 w-full" />
      <Skeleton className="h-12 w-full" />
    </div>
  );
}

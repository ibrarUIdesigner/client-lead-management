import { cn } from "../../lib/cn";

type SkeletonProps = {
  className?: string;
};

export function Skeleton({ className }: SkeletonProps) {
  return (
    <div
      className={cn(
        "animate-pulse rounded-control bg-gray-100 motion-reduce:animate-none",
        className,
      )}
    />
  );
}

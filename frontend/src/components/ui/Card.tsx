import type { ReactNode } from "react";

import { cn } from "../../lib/cn";

type CardProps = {
  children: ReactNode;
  className?: string;
};

export function Card({ children, className }: CardProps) {
  return (
    <div className={cn("rounded-card border border-gray-200/85 bg-white shadow-2xs p-4 sm:p-6", className)}>
      {children}
    </div>
  );
}

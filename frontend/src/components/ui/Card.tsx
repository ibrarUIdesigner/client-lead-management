import type { ReactNode } from "react";

import { cn } from "../../lib/cn";

type CardProps = {
  children: ReactNode;
  className?: string;
};

export function Card({ children, className }: CardProps) {
  return (
    <div className={cn("rounded-card border border-gray-200 bg-white p-6", className)}>
      {children}
    </div>
  );
}

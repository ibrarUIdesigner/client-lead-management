import type { ButtonHTMLAttributes, ReactNode } from "react";

import { cn, focusRing } from "../../lib/cn";
import { Spinner } from "./Spinner";

type ButtonProps = ButtonHTMLAttributes<HTMLButtonElement> & {
  variant?: "primary" | "secondary" | "ghost";
  size?: "default" | "icon";
  isLoading?: boolean;
  children: ReactNode;
};

const variants = {
  primary: "bg-primary text-white hover:bg-primary-hover",
  secondary: "border border-gray-300 bg-white text-gray-700 hover:bg-gray-50",
  ghost: "text-gray-600 hover:bg-gray-100",
};

export function Button({
  variant = "primary",
  size = "default",
  isLoading = false,
  className,
  type = "button",
  disabled,
  children,
  ...props
}: ButtonProps) {
  return (
    <button
      type={type}
      disabled={disabled || isLoading}
      className={cn(
        "inline-flex items-center justify-center gap-2 rounded-control text-body font-semibold transition-colors duration-150 disabled:cursor-not-allowed disabled:opacity-50",
        focusRing,
        size === "icon" ? "size-11 lg:size-10" : "h-11 px-4 lg:h-10",
        variants[variant],
        className,
      )}
      {...props}
    >
      {isLoading ? <Spinner /> : null}
      {children}
    </button>
  );
}

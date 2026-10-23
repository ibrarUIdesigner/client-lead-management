import type { ButtonHTMLAttributes, ReactNode } from "react";

import { cn, focusRing } from "../../lib/cn";
import { Spinner } from "./Spinner";

type ButtonProps = ButtonHTMLAttributes<HTMLButtonElement> & {
  variant?: "primary" | "secondary" | "ghost" | "danger";
  size?: "default" | "sm" | "lg" | "icon" | "icon-sm";
  isLoading?: boolean;
  children: ReactNode;
};

const variants = {
  primary:
    "bg-primary text-white shadow-2xs hover:bg-primary-hover active:bg-primary-700 active:scale-[0.99] transition-all",
  secondary:
    "border border-gray-200 bg-white text-gray-700 shadow-2xs hover:bg-gray-50 hover:border-gray-300 hover:text-ink active:bg-gray-100 active:scale-[0.99] transition-all",
  ghost:
    "text-gray-600 hover:bg-gray-100/80 hover:text-ink active:bg-gray-200/50 transition-colors",
  danger:
    "bg-danger text-white shadow-2xs hover:bg-red-600 active:bg-red-700 active:scale-[0.99] transition-all",
};

const sizes = {
  default: "h-11 px-4 text-body font-semibold lg:h-10",
  sm: "h-8 px-3 text-small font-medium",
  lg: "h-12 px-5 text-body-lg font-semibold lg:h-11",
  icon: "size-11 lg:size-10 shrink-0",
  "icon-sm": "size-8 shrink-0",
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
        "inline-flex items-center justify-center gap-2 rounded-control select-none disabled:cursor-not-allowed disabled:opacity-50",
        focusRing,
        sizes[size],
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

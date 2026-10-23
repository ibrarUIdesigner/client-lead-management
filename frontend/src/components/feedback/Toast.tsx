import { useCallback, useEffect, useMemo, useRef, useState, type ReactNode } from "react";
import { AnimatePresence, motion, useReducedMotion } from "framer-motion";
import { AlertCircle, CheckCircle2, Info, X } from "lucide-react";

import { ToastContext, type ToastTone } from "./useToast";
import { cn } from "../../lib/cn";

type ToastRecord = {
  id: string;
  message: string;
  tone: ToastTone;
};

const toneStyles: Record<
  ToastTone,
  { icon: typeof Info; iconClass: string; borderClass: string }
> = {
  info: {
    icon: Info,
    iconClass: "text-blue-600",
    borderClass: "border-l-primary-500",
  },
  success: {
    icon: CheckCircle2,
    iconClass: "text-emerald-600",
    borderClass: "border-l-emerald-500",
  },
  danger: {
    icon: AlertCircle,
    iconClass: "text-danger",
    borderClass: "border-l-danger",
  },
};

export function ToastProvider({ children }: { children: ReactNode }) {
  const [toasts, setToasts] = useState<ToastRecord[]>([]);
  const reduceMotion = useReducedMotion();
  const timeouts = useRef<number[]>([]);

  useEffect(() => {
    const pending = timeouts.current;
    return () => {
      pending.forEach((timeoutId) => {
        window.clearTimeout(timeoutId);
      });
    };
  }, []);

  const dismiss = useCallback((id: string) => {
    setToasts((current) => current.filter((toast) => toast.id !== id));
  }, []);

  const notify = useCallback(
    (message: string, tone: ToastTone = "info") => {
      const id = crypto.randomUUID();
      setToasts((current) => [...current, { id, message, tone }]);
      const timeoutId = window.setTimeout(() => {
        dismiss(id);
      }, 4000);
      timeouts.current.push(timeoutId);
    },
    [dismiss],
  );

  const value = useMemo(() => ({ notify }), [notify]);

  return (
    <ToastContext.Provider value={value}>
      {children}
      <div
        className="pointer-events-none fixed inset-x-4 bottom-4 z-50 flex flex-col gap-2 sm:left-auto sm:right-6 sm:w-88"
        aria-live="polite"
      >
        <AnimatePresence>
          {toasts.map((toast) => {
            const config = toneStyles[toast.tone] ?? toneStyles.info;
            const Icon = config.icon;

            return (
              <motion.div
                key={toast.id}
                role="status"
                initial={reduceMotion ? false : { opacity: 0, y: 8, scale: 0.98 }}
                animate={{ opacity: 1, y: 0, scale: 1 }}
                exit={reduceMotion ? undefined : { opacity: 0, y: 8, scale: 0.98 }}
                transition={{ duration: 0.16 }}
                className={cn(
                  "pointer-events-auto flex items-start gap-3 rounded-card border border-gray-200 border-l-4 bg-white p-3.5 shadow-lg text-body text-ink",
                  config.borderClass,
                )}
              >
                <Icon className={cn("size-4.5 shrink-0 mt-0.5", config.iconClass)} aria-hidden="true" />
                <p className="flex-1 text-small font-medium leading-normal text-ink">
                  {toast.message}
                </p>
                <button
                  type="button"
                  onClick={() => dismiss(toast.id)}
                  aria-label="Dismiss notification"
                  className="rounded-md p-1 text-gray-400 hover:bg-gray-100 hover:text-ink transition-colors"
                >
                  <X className="size-3.5" aria-hidden="true" />
                </button>
              </motion.div>
            );
          })}
        </AnimatePresence>
      </div>
    </ToastContext.Provider>
  );
}

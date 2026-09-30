import { useCallback, useEffect, useMemo, useRef, useState, type ReactNode } from "react";
import { AnimatePresence, motion, useReducedMotion } from "framer-motion";

import { ToastContext, type ToastTone } from "./useToast";

type ToastRecord = {
  id: string;
  message: string;
  tone: ToastTone;
};

const toneBorder: Record<ToastTone, string> = {
  info: "border-l-info",
  success: "border-l-success",
  danger: "border-l-danger",
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
        className="pointer-events-none fixed inset-x-4 bottom-4 z-50 flex flex-col gap-2 sm:left-auto sm:right-6 sm:w-80"
        aria-live="polite"
      >
        <AnimatePresence>
          {toasts.map((toast) => (
            <motion.div
              key={toast.id}
              role="status"
              initial={reduceMotion ? false : { opacity: 0, y: 8 }}
              animate={{ opacity: 1, y: 0 }}
              exit={reduceMotion ? undefined : { opacity: 0, y: 8 }}
              transition={{ duration: 0.18 }}
              className={`pointer-events-auto rounded-card border border-gray-200 border-l-4 bg-white px-4 py-3 text-body text-ink shadow-md ${toneBorder[toast.tone]}`}
            >
              {toast.message}
            </motion.div>
          ))}
        </AnimatePresence>
      </div>
    </ToastContext.Provider>
  );
}

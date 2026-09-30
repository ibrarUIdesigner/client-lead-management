import { useEffect, useId, type ReactNode } from "react";
import { AnimatePresence, motion, useReducedMotion } from "framer-motion";
import { X } from "lucide-react";

import { Button } from "./Button";

type DrawerProps = {
  open: boolean;
  title: string;
  onClose: () => void;
  children: ReactNode;
};

export function Drawer({ open, title, onClose, children }: DrawerProps) {
  const titleId = useId();
  const reduceMotion = useReducedMotion();

  useEffect(() => {
    if (!open) {
      return;
    }

    const onKeyDown = (event: KeyboardEvent) => {
      if (event.key === "Escape") {
        onClose();
      }
    };

    const previousOverflow = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    document.addEventListener("keydown", onKeyDown);

    return () => {
      document.body.style.overflow = previousOverflow;
      document.removeEventListener("keydown", onKeyDown);
    };
  }, [open, onClose]);

  return (
    <AnimatePresence>
      {open ? (
        <div className="fixed inset-0 z-40">
          <motion.button
            type="button"
            aria-label="Close menu"
            className="absolute inset-0 bg-ink/40"
            initial={reduceMotion ? false : { opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={reduceMotion ? undefined : { opacity: 0 }}
            transition={{ duration: 0.18 }}
            onClick={onClose}
          />
          <motion.aside
            role="dialog"
            aria-modal="true"
            aria-labelledby={titleId}
            className="absolute inset-y-0 left-0 flex w-sidebar max-w-[85vw] flex-col bg-white shadow-lg"
            initial={reduceMotion ? false : { x: -248 }}
            animate={{ x: 0 }}
            exit={reduceMotion ? undefined : { x: -248 }}
            transition={{ duration: 0.18 }}
          >
            <div className="flex h-topbar items-center justify-between px-4">
              <h2 id={titleId} className="text-h4 font-semibold text-ink">
                {title}
              </h2>
              <Button variant="ghost" size="icon" aria-label="Close" onClick={onClose}>
                <X size={18} aria-hidden="true" />
              </Button>
            </div>
            <div className="flex-1 overflow-y-auto px-3 pb-6">{children}</div>
          </motion.aside>
        </div>
      ) : null}
    </AnimatePresence>
  );
}

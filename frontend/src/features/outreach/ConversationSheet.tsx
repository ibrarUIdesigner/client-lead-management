import { useEffect, useId } from "react";
import { Link } from "react-router-dom";
import { AnimatePresence, motion, useReducedMotion } from "framer-motion";
import { X } from "lucide-react";

import { Button } from "../../components/ui/Button";
import { ConversationPanel } from "../gmail/ConversationPanel";
import { cn, focusRing } from "../../lib/cn";
import type { OutreachMessageItem } from "../../types/workspace";

type ConversationSheetProps = {
  item: OutreachMessageItem | null;
  onClose: () => void;
};

export function ConversationSheet({ item, onClose }: ConversationSheetProps) {
  const titleId = useId();
  const reduceMotion = useReducedMotion();
  const open = item !== null;

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
      {item ? (
        <div className="fixed inset-0 z-40">
          <motion.button
            type="button"
            aria-label="Close conversation"
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
            className="absolute inset-y-0 right-0 flex w-full max-w-2xl flex-col bg-white shadow-lg"
            initial={reduceMotion ? false : { x: 48 }}
            animate={{ x: 0 }}
            exit={reduceMotion ? undefined : { x: 48 }}
            transition={{ duration: 0.18 }}
          >
            <div className="flex items-start justify-between gap-3 border-b border-gray-100 px-5 py-4">
              <div>
                <h2 id={titleId} className="text-h4 font-semibold text-ink">
                  {item.business_name}
                </h2>
                <p className="mt-1 text-small text-gray-600">
                  {item.subject || "No subject"}
                </p>
                <Link
                  to={`/leads/${item.lead_id}`}
                  className={cn(
                    "mt-2 inline-flex text-small font-semibold text-primary-700",
                    focusRing,
                  )}
                >
                  Open lead
                </Link>
              </div>
              <Button variant="ghost" size="icon" aria-label="Close" onClick={onClose}>
                <X size={18} aria-hidden="true" />
              </Button>
            </div>
            <div className="flex-1 overflow-y-auto px-5 py-5">
              <ConversationPanel leadId={item.lead_id} />
            </div>
          </motion.aside>
        </div>
      ) : null}
    </AnimatePresence>
  );
}

import { useEffect, useId, useRef, type ReactNode } from "react";
import { X } from "lucide-react";

import { Button } from "./Button";
import { cn } from "../../lib/cn";

type ModalProps = {
  open: boolean;
  title: string;
  description?: string;
  size?: "md" | "lg" | "xl";
  onClose: () => void;
  children: ReactNode;
};

export function Modal({
  open,
  title,
  description,
  size = "md",
  onClose,
  children,
}: ModalProps) {
  const dialogRef = useRef<HTMLDialogElement>(null);
  const titleId = useId();

  useEffect(() => {
    const dialog = dialogRef.current;
    if (!dialog) {
      return;
    }

    if (open && !dialog.open) {
      dialog.showModal();
    } else if (!open && dialog.open) {
      dialog.close();
    }
  }, [open]);

  return (
    <dialog
      ref={dialogRef}
      aria-labelledby={titleId}
      className={cn(
        "text-ink",
        size === "lg" && "dialog-lg",
        size === "xl" && "dialog-xl",
      )}
      onClose={onClose}
    >
      <div className="flex items-start justify-between gap-4 border-b border-gray-100 p-5 sm:p-6 pb-4">
        <div>
          <h2 id={titleId} className="text-h4 font-bold text-ink sm:text-h3">
            {title}
          </h2>
          {description ? <p className="mt-1 text-small text-gray-500 leading-normal">{description}</p> : null}
        </div>
        <Button
          variant="ghost"
          size="icon-sm"
          className="text-gray-400 hover:text-ink shrink-0 -mr-1"
          aria-label="Close"
          onClick={onClose}
        >
          <X size={18} aria-hidden="true" />
        </Button>
      </div>
      <div className="p-5 sm:p-6">{children}</div>
    </dialog>
  );
}

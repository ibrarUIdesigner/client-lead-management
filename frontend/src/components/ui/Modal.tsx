import { useEffect, useId, useRef, type ReactNode } from "react";
import { X } from "lucide-react";

import { Button } from "./Button";

type ModalProps = {
  open: boolean;
  title: string;
  description?: string;
  onClose: () => void;
  children: ReactNode;
};

export function Modal({ open, title, description, onClose, children }: ModalProps) {
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
    <dialog ref={dialogRef} aria-labelledby={titleId} className="text-ink" onClose={onClose}>
      <div className="flex items-start justify-between gap-4 p-6 pb-0">
        <div>
          <h2 id={titleId} className="text-h3 font-semibold">
            {title}
          </h2>
          {description ? <p className="mt-2 text-body text-gray-600">{description}</p> : null}
        </div>
        <Button variant="ghost" size="icon" aria-label="Close" onClick={onClose}>
          <X size={18} aria-hidden="true" />
        </Button>
      </div>
      <div className="p-6">{children}</div>
    </dialog>
  );
}

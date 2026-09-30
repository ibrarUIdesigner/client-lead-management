import { Menu } from "lucide-react";

import { Button } from "../ui/Button";

type TopbarProps = {
  onOpenMenu: () => void;
};

export function Topbar({ onOpenMenu }: TopbarProps) {
  return (
    <header className="sticky top-0 z-20 flex h-topbar items-center gap-3 border-b border-gray-200 bg-white px-4 lg:px-10">
      <Button
        variant="ghost"
        size="icon"
        className="lg:hidden"
        aria-label="Open menu"
        onClick={onOpenMenu}
      >
        <Menu size={18} aria-hidden="true" />
      </Button>
      <p className="text-h4 font-semibold text-ink lg:hidden">Client Acquisition</p>
    </header>
  );
}

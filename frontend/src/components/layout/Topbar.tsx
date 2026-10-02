import { LogOut, Menu, PanelLeftClose, PanelLeftOpen } from "lucide-react";
import { useNavigate } from "react-router-dom";

import { signOut } from "../../lib/auth";
import { Button } from "../ui/Button";

type TopbarProps = {
  collapsed: boolean;
  onOpenMenu: () => void;
  onToggleSidebar: () => void;
};

export function Topbar({ collapsed, onOpenMenu, onToggleSidebar }: TopbarProps) {
  const navigate = useNavigate();

  return (
    <header className="sticky top-0 z-20 flex h-topbar items-center gap-2 border-b border-gray-200 bg-white px-4 sm:gap-3 lg:px-8">
      <Button
        variant="ghost"
        size="icon"
        className="lg:hidden"
        aria-label="Open menu"
        onClick={onOpenMenu}
      >
        <Menu size={18} aria-hidden="true" />
      </Button>
      <div className="hidden lg:block">
        <Button
          variant="ghost"
          size="icon"
          aria-expanded={!collapsed}
          aria-label={collapsed ? "Expand sidebar" : "Collapse sidebar"}
          onClick={onToggleSidebar}
        >
          {collapsed ? (
            <PanelLeftOpen size={18} aria-hidden="true" />
          ) : (
            <PanelLeftClose size={18} aria-hidden="true" />
          )}
        </Button>
      </div>
      <p className="truncate text-h4 font-semibold text-ink lg:hidden">Client Acquisition</p>
      <Button
        variant="ghost"
        className="ml-auto shrink-0"
        aria-label="Sign out"
        onClick={() => {
          signOut();
          navigate("/login", { replace: true });
        }}
      >
        <LogOut size={16} aria-hidden="true" />
        <span className="hidden sm:inline">Sign out</span>
      </Button>
    </header>
  );
}

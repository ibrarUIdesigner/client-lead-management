import { useState, useEffect } from "react";
import { LogOut, Menu, PanelLeftClose, PanelLeftOpen, Search } from "lucide-react";
import { useNavigate } from "react-router-dom";

import { signOut } from "../../lib/auth";
import { Button } from "../ui/Button";
import { CommandPalette } from "./CommandPalette";
import { QuickNewDropdown } from "./QuickNewDropdown";

type TopbarProps = {
  collapsed: boolean;
  onOpenMenu: () => void;
  onToggleSidebar: () => void;
};

export function Topbar({ collapsed, onOpenMenu, onToggleSidebar }: TopbarProps) {
  const navigate = useNavigate();
  const [commandPaletteOpen, setCommandPaletteOpen] = useState(false);

  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if ((e.ctrlKey || e.metaKey) && e.key === "k") {
        e.preventDefault();
        setCommandPaletteOpen((prev) => !prev);
      }
    };
    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, []);

  return (
    <>
      <header className="sticky top-0 z-20 flex h-topbar items-center justify-between gap-2 border-b border-gray-200 bg-white/95 backdrop-blur-xs px-4 sm:gap-3 lg:px-8">
        <div className="flex items-center gap-2 sm:gap-3">
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
          <p className="truncate text-h4 font-bold text-ink lg:hidden">Client Acquisition</p>
        </div>

        {/* Global Search Bar (⌘K / Ctrl+K trigger) */}
        <div className="flex-1 max-w-md mx-2 hidden sm:block">
          <button
            type="button"
            onClick={() => setCommandPaletteOpen(true)}
            className="flex w-full items-center justify-between rounded-control border border-gray-200 bg-gray-50/70 px-3 py-1.5 text-small text-gray-500 hover:border-gray-300 hover:bg-white transition-all shadow-2xs"
          >
            <div className="flex items-center gap-2">
              <Search className="size-4 text-gray-400" />
              <span>Search leads, websites, mockups...</span>
            </div>
            <kbd className="inline-flex items-center rounded border border-gray-200 bg-white px-1.5 py-0.5 text-[11px] font-semibold text-gray-400 shadow-2xs">
              Ctrl K
            </kbd>
          </button>
        </div>

        {/* Right side controls: Mobile search button, Quick New Dropdown, Sign Out */}
        <div className="flex items-center gap-2">
          <Button
            variant="ghost"
            size="icon"
            className="sm:hidden text-gray-500"
            aria-label="Search"
            onClick={() => setCommandPaletteOpen(true)}
          >
            <Search size={18} aria-hidden="true" />
          </Button>

          <QuickNewDropdown />

          <Button
            variant="ghost"
            className="h-8 text-gray-600 hover:text-danger gap-1.5 px-2.5 text-small"
            aria-label="Sign out"
            onClick={() => {
              signOut();
              navigate("/login", { replace: true });
            }}
          >
            <LogOut size={16} aria-hidden="true" />
            <span className="hidden md:inline">Sign out</span>
          </Button>
        </div>
      </header>

      <CommandPalette
        open={commandPaletteOpen}
        onClose={() => setCommandPaletteOpen(false)}
      />
    </>
  );
}

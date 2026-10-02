import { PanelLeftClose, PanelLeftOpen } from "lucide-react";

import { cn } from "../../lib/cn";
import { Button } from "../ui/Button";
import { SidebarNav } from "./SidebarNav";

type SidebarProps = {
  collapsed: boolean;
  onToggle: () => void;
};

export function Sidebar({ collapsed, onToggle }: SidebarProps) {
  return (
    <aside
      className={cn(
        "fixed inset-y-0 left-0 z-30 hidden flex-col border-r border-gray-200 bg-white transition-[width] duration-200 ease-out motion-reduce:transition-none lg:flex",
        collapsed ? "w-sidebar-rail" : "w-sidebar",
      )}
    >
      <div
        className={cn(
          "flex h-topbar items-center",
          collapsed ? "justify-center px-2" : "gap-2 px-4",
        )}
      >
        <span className="inline-flex size-8 shrink-0 items-center justify-center rounded-control bg-primary text-caption font-semibold text-white">
          CA
        </span>
        {collapsed ? null : (
          <p className="min-w-0 truncate text-h4 font-semibold text-ink">Client Acquisition</p>
        )}
      </div>
      <div className={cn("min-h-0 flex-1 overflow-y-auto", collapsed ? "px-2" : "px-3")}>
        <SidebarNav collapsed={collapsed} />
      </div>
      <div className={cn("border-t border-gray-200 p-2", collapsed ? "flex justify-center" : "px-3")}>
        <Button
          variant="ghost"
          size={collapsed ? "icon" : "default"}
          aria-expanded={!collapsed}
          aria-label={collapsed ? "Expand sidebar" : "Collapse sidebar"}
          className={collapsed ? undefined : "w-full justify-start"}
          onClick={onToggle}
        >
          {collapsed ? (
            <PanelLeftOpen size={18} aria-hidden="true" />
          ) : (
            <PanelLeftClose size={18} aria-hidden="true" />
          )}
          {collapsed ? null : "Collapse"}
        </Button>
      </div>
    </aside>
  );
}

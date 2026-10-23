import { Layers, PanelLeftClose, PanelLeftOpen } from "lucide-react";

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
        "fixed inset-y-0 left-0 z-30 hidden flex-col border-r border-gray-200/90 bg-white transition-[width] duration-200 ease-out motion-reduce:transition-none lg:flex",
        collapsed ? "w-sidebar-rail" : "w-sidebar",
      )}
    >
      <div
        className={cn(
          "flex h-topbar items-center border-b border-gray-100",
          collapsed ? "justify-center px-2" : "gap-3 px-4",
        )}
      >
        <div className="flex size-9 shrink-0 items-center justify-center rounded-lg bg-gradient-to-br from-primary-600 to-primary-700 text-white shadow-xs ring-1 ring-black/5">
          <Layers className="size-5" aria-hidden="true" />
        </div>
        {collapsed ? null : (
          <div className="min-w-0 flex-1">
            <p className="truncate text-body font-bold tracking-tight text-ink">
              Client Acquisition
            </p>
            <p className="text-[10px] font-semibold uppercase tracking-wider text-gray-400">
              Growth Workspace
            </p>
          </div>
        )}
      </div>
      <div className={cn("min-h-0 flex-1 overflow-y-auto py-2", collapsed ? "px-2" : "px-3")}>
        <SidebarNav collapsed={collapsed} />
      </div>
      <div className={cn("border-t border-gray-100 p-2", collapsed ? "flex justify-center" : "px-3")}>
        <Button
          variant="ghost"
          size={collapsed ? "icon" : "default"}
          aria-expanded={!collapsed}
          aria-label={collapsed ? "Expand sidebar" : "Collapse sidebar"}
          className={cn(
            "text-gray-500 hover:text-ink hover:bg-gray-100/70",
            collapsed ? "size-10" : "w-full justify-start gap-2.5 px-3 h-9 text-small",
          )}
          onClick={onToggle}
        >
          {collapsed ? (
            <PanelLeftOpen size={18} aria-hidden="true" />
          ) : (
            <PanelLeftClose size={18} aria-hidden="true" />
          )}
          {collapsed ? null : <span>Collapse sidebar</span>}
        </Button>
      </div>
    </aside>
  );
}

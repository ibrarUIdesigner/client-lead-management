import { useState } from "react";
import { NavLink } from "react-router-dom";
import { HelpCircle } from "lucide-react";

import { navigationGroups, utilityNavItems } from "../../app/navigation";
import { cn, focusRing } from "../../lib/cn";
import { HelpModal } from "./HelpModal";

type SidebarNavProps = {
  collapsed?: boolean;
  onNavigate?: () => void;
};

export function SidebarNav({ collapsed = false, onNavigate }: SidebarNavProps) {
  const [helpOpen, setHelpOpen] = useState(false);

  return (
    <>
      <nav aria-label="Main Navigation" className="flex flex-col gap-5 py-2">
        {navigationGroups.map((group) => (
          <div key={group.title} className="flex flex-col gap-1">
            {!collapsed ? (
              <span className="px-3 pb-1 text-[11px] font-bold tracking-wider text-gray-400 uppercase">
                {group.title}
              </span>
            ) : null}

            {group.items.map((item) => {
              const Icon = item.icon;
              return (
                <NavLink
                  key={item.to}
                  to={item.to}
                  end={item.end}
                  title={collapsed ? item.label : undefined}
                  onClick={onNavigate}
                  className={({ isActive }) =>
                    cn(
                      "flex min-h-10 items-center rounded-control text-small font-medium text-gray-600 transition-colors",
                      focusRing,
                      collapsed ? "justify-center px-0" : "gap-3 px-3",
                      isActive
                        ? "bg-primary-50 font-semibold text-primary-700 shadow-2xs"
                        : "hover:bg-gray-100/80 hover:text-ink",
                    )
                  }
                >
                  <Icon size={18} aria-hidden="true" className="shrink-0" />
                  {!collapsed ? (
                    <span className="truncate">{item.label}</span>
                  ) : (
                    <span className="sr-only">{item.label}</span>
                  )}
                  {!collapsed && item.badge ? (
                    <span className="ml-auto rounded-full bg-primary-100 px-2 py-0.5 text-[10px] font-bold text-primary-700">
                      {item.badge}
                    </span>
                  ) : null}
                </NavLink>
              );
            })}
          </div>
        ))}

        {/* Utility section */}
        <div className="flex flex-col gap-1 border-t border-gray-100 pt-3">
          {!collapsed ? (
            <span className="px-3 pb-1 text-[11px] font-bold tracking-wider text-gray-400 uppercase">
              UTILITIES
            </span>
          ) : null}

          {utilityNavItems.map((item) => {
            const Icon = item.icon;
            return (
              <NavLink
                key={item.to}
                to={item.to}
                end={item.end}
                title={collapsed ? item.label : undefined}
                onClick={onNavigate}
                className={({ isActive }) =>
                  cn(
                    "flex min-h-10 items-center rounded-control text-small font-medium text-gray-600 transition-colors",
                    focusRing,
                    collapsed ? "justify-center px-0" : "gap-3 px-3",
                    isActive
                      ? "bg-primary-50 font-semibold text-primary-700 shadow-2xs"
                      : "hover:bg-gray-100/80 hover:text-ink",
                  )
                }
              >
                <Icon size={18} aria-hidden="true" className="shrink-0" />
                {!collapsed ? (
                  <span className="truncate">{item.label}</span>
                ) : (
                  <span className="sr-only">{item.label}</span>
                )}
              </NavLink>
            );
          })}

          <button
            type="button"
            title={collapsed ? "Help & Workflow" : undefined}
            onClick={() => setHelpOpen(true)}
            className={cn(
              "flex min-h-10 items-center rounded-control text-small font-medium text-gray-600 transition-colors hover:bg-gray-100/80 hover:text-ink text-left",
              focusRing,
              collapsed ? "justify-center px-0" : "gap-3 px-3",
            )}
          >
            <HelpCircle size={18} aria-hidden="true" className="shrink-0 text-gray-500" />
            {!collapsed ? <span>Workflow Guide</span> : <span className="sr-only">Workflow Guide</span>}
          </button>
        </div>
      </nav>

      <HelpModal open={helpOpen} onClose={() => setHelpOpen(false)} />
    </>
  );
}

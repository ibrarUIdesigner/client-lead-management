import { NavLink } from "react-router-dom";

import { navItems } from "../../app/navigation";
import { cn, focusRing } from "../../lib/cn";

type SidebarNavProps = {
  collapsed?: boolean;
  onNavigate?: () => void;
};

export function SidebarNav({ collapsed = false, onNavigate }: SidebarNavProps) {
  return (
    <nav aria-label="Main" className="flex flex-col gap-1">
      {navItems.map((item) => {
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
                "flex min-h-11 items-center rounded-control text-body font-medium text-gray-600",
                focusRing,
                collapsed ? "justify-center px-0" : "gap-3 px-3",
                isActive && "bg-primary-50 text-primary-700",
              )
            }
          >
            <Icon size={18} aria-hidden="true" />
            <span className={cn(collapsed && "sr-only")}>{item.label}</span>
          </NavLink>
        );
      })}
    </nav>
  );
}

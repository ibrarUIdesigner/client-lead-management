import { NavLink } from "react-router-dom";

import { navItems } from "../../app/navigation";
import { cn, focusRing } from "../../lib/cn";

type SidebarNavProps = {
  onNavigate?: () => void;
};

export function SidebarNav({ onNavigate }: SidebarNavProps) {
  return (
    <nav aria-label="Main" className="flex flex-col gap-1">
      {navItems.map((item) => {
        const Icon = item.icon;

        return (
          <NavLink
            key={item.to}
            to={item.to}
            end={item.end}
            onClick={onNavigate}
            className={({ isActive }) =>
              cn(
                "flex min-h-11 items-center gap-3 rounded-control px-3 text-body font-medium text-gray-600",
                focusRing,
                isActive && "bg-primary-50 text-primary-700",
              )
            }
          >
            <Icon size={18} aria-hidden="true" />
            {item.label}
          </NavLink>
        );
      })}
    </nav>
  );
}

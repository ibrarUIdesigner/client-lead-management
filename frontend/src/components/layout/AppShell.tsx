import { useEffect, useState } from "react";
import { Outlet, useLocation } from "react-router-dom";

import { useOnline } from "../../hooks/useOnline";
import { Drawer } from "../ui/Drawer";
import { cn } from "../../lib/cn";
import { Sidebar } from "./Sidebar";
import { SidebarNav } from "./SidebarNav";
import { Topbar } from "./Topbar";
import { useSidebarCollapsed } from "./useSidebarCollapsed";

export function AppShell() {
  const [menuOpen, setMenuOpen] = useState(false);
  const { collapsed, toggle } = useSidebarCollapsed();
  const online = useOnline();
  const location = useLocation();
  const wide =
    location.pathname === "/leads" ||
    location.pathname === "/apify" ||
    location.pathname.startsWith("/design-md");

  useEffect(() => {
    const media = window.matchMedia("(min-width: 1024px)");
    const closeOnDesktop = () => {
      if (media.matches) {
        setMenuOpen(false);
      }
    };

    media.addEventListener("change", closeOnDesktop);
    return () => {
      media.removeEventListener("change", closeOnDesktop);
    };
  }, []);

  return (
    <div className="min-h-screen bg-background text-ink">
      <a
        href="#main"
        className="sr-only focus:not-sr-only focus:absolute focus:top-3 focus:left-3 focus:z-50 focus:rounded-control focus:bg-white focus:px-3 focus:py-2"
      >
        Skip to content
      </a>
      <Sidebar collapsed={collapsed} onToggle={toggle} />
      <Drawer
        open={menuOpen}
        title="Menu"
        onClose={() => {
          setMenuOpen(false);
        }}
      >
        <SidebarNav
          onNavigate={() => {
            setMenuOpen(false);
          }}
        />
      </Drawer>
      <div
        className={cn(
          "min-w-0 transition-[padding] duration-200 ease-out motion-reduce:transition-none",
          collapsed ? "lg:pl-sidebar-rail" : "lg:pl-sidebar",
        )}
      >
        <Topbar
          collapsed={collapsed}
          onOpenMenu={() => {
            setMenuOpen(true);
          }}
          onToggleSidebar={toggle}
        />
        {online ? null : (
          <p
            className="border-b border-amber-200 bg-amber-50 px-4 py-2 text-small text-amber-950 lg:px-10"
            role="status"
          >
            You are offline. Pages that need the server will not refresh until the connection returns.
          </p>
        )}
        <main
          id="main"
          className={cn(
            "mx-auto w-full px-4 py-6 md:px-8 md:py-8 lg:px-10",
            wide ? "max-w-none" : "max-w-[1440px]",
          )}
        >
          <Outlet />
        </main>
      </div>
    </div>
  );
}

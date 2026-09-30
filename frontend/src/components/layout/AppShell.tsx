import { useEffect, useState } from "react";
import { Outlet } from "react-router-dom";

import { Drawer } from "../ui/Drawer";
import { Sidebar } from "./Sidebar";
import { SidebarNav } from "./SidebarNav";
import { Topbar } from "./Topbar";

export function AppShell() {
  const [menuOpen, setMenuOpen] = useState(false);

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
      <Sidebar />
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
      <div className="lg:pl-sidebar">
        <Topbar
          onOpenMenu={() => {
            setMenuOpen(true);
          }}
        />
        <main
          id="main"
          className="mx-auto w-full max-w-[1440px] px-4 py-6 md:px-8 md:py-8 lg:px-10"
        >
          <Outlet />
        </main>
      </div>
    </div>
  );
}

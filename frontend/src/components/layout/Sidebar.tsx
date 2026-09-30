import { SidebarNav } from "./SidebarNav";

export function Sidebar() {
  return (
    <aside className="fixed inset-y-0 left-0 z-30 hidden w-sidebar flex-col border-r border-gray-200 bg-white lg:flex">
      <div className="flex h-topbar items-center px-5">
        <p className="text-h4 font-semibold text-ink">Client Acquisition</p>
      </div>
      <div className="px-3">
        <SidebarNav />
      </div>
    </aside>
  );
}

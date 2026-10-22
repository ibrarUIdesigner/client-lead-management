import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import {
  ArrowRight,
  Bot,
  CalendarClock,
  Compass,
  FileSpreadsheet,
  Flame,
  Globe,
  Images,
  Mail,
  MapPin,
  Plus,
  Search,
  Users,
  X,
} from "lucide-react";

import { useLeads } from "../../hooks/useLeads";
import { useMockups } from "../../hooks/useWorkspace";
import { StatusBadge } from "../ui/Badge";

type CommandPaletteProps = {
  open: boolean;
  onClose: () => void;
};

export function CommandPalette({ open, onClose }: CommandPaletteProps) {
  const navigate = useNavigate();
  const [query, setQuery] = useState("");
  const trimmed = query.trim();

  // Search leads using API query
  const leadsQuery = useLeads({
    q: trimmed || undefined,
    limit: 8,
    direction: "desc",
    sort: "lead_score",
  });

  const mockupsQuery = useMockups();

  // Global hotkey Ctrl+K / Cmd+K listener
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if ((e.ctrlKey || e.metaKey) && e.key === "k") {
        e.preventDefault();
        if (open) {
          onClose();
        }
      }
      if (e.key === "Escape" && open) {
        onClose();
      }
    };
    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, [open, onClose]);

  if (!open) return null;

  const leads = leadsQuery.data?.items ?? [];
  const mockups = (mockupsQuery.data ?? []).filter(
    (m) =>
      trimmed &&
      (m.business_name?.toLowerCase().includes(trimmed.toLowerCase()) ||
        m.title?.toLowerCase().includes(trimmed.toLowerCase())),
  );

  const quickNavItems = [
    { label: "Find new leads", to: "/discover", icon: Compass, badge: "Discovery" },
    { label: "Add single lead", to: "/leads/new", icon: Plus, badge: "Manual" },
    { label: "Import CSV leads", to: "/leads/import", icon: FileSpreadsheet, badge: "Import" },
    { label: "Sales pipeline", to: "/pipeline", icon: Users, badge: "Pipeline" },
    { label: "Homepage mockups", to: "/mockups", icon: Images, badge: "Creative" },
    { label: "Outreach & Gmail", to: "/outreach", icon: Mail, badge: "Sales" },
    { label: "Follow-ups scheduler", to: "/follow-ups", icon: CalendarClock, badge: "Tasks" },
    { label: "Apify actor automation", to: "/apify", icon: Bot, badge: "Automation" },
  ].filter(
    (item) =>
      !trimmed || item.label.toLowerCase().includes(trimmed.toLowerCase()),
  );

  return (
    <div
      className="fixed inset-0 z-50 flex items-start justify-center bg-ink/40 p-4 pt-16 sm:pt-24 backdrop-blur-xs animate-in fade-in duration-150"
      onClick={onClose}
      role="dialog"
      aria-modal="true"
    >
      <div
        className="relative w-full max-w-2xl overflow-hidden rounded-2xl border border-gray-200 bg-white shadow-2xl animate-in zoom-in-95 duration-150"
        onClick={(e) => e.stopPropagation()}
      >
        {/* Search Input Bar */}
        <div className="flex items-center gap-3 border-b border-gray-100 px-4 py-3.5 sm:px-5">
          <Search className="size-5 shrink-0 text-gray-400" />
          <input
            type="text"
            autoFocus
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder="Search leads, businesses, locations, websites, mockups... (Esc to close)"
            className="w-full bg-transparent text-body font-medium text-ink placeholder-gray-400 focus:outline-none"
          />
          {query ? (
            <button
              type="button"
              onClick={() => setQuery("")}
              className="text-gray-400 hover:text-gray-600"
            >
              <X className="size-4" />
            </button>
          ) : (
            <kbd className="hidden sm:inline-flex items-center rounded border border-gray-200 bg-gray-50 px-2 py-0.5 text-caption font-semibold text-gray-500">
              ESC
            </kbd>
          )}
        </div>

        {/* Results Area */}
        <div className="max-h-[60vh] overflow-y-auto p-2 sm:p-3 space-y-4">
          {/* Matching Leads */}
          {leads.length > 0 ? (
            <div>
              <p className="px-3 py-1.5 text-caption font-semibold uppercase tracking-wider text-gray-400">
                Prospects & Leads ({leads.length})
              </p>
              <div className="mt-1 space-y-1">
                {leads.map((lead) => (
                  <button
                    key={lead.id}
                    type="button"
                    onClick={() => {
                      onClose();
                      navigate(`/leads/${lead.id}`);
                    }}
                    className="flex w-full items-center justify-between gap-3 rounded-xl px-3 py-2.5 text-left transition-colors hover:bg-primary-50/70 group"
                  >
                    <div className="min-w-0 flex-1">
                      <div className="flex items-center gap-2">
                        <span className="font-semibold text-ink group-hover:text-primary-700 truncate">
                          {lead.business_name}
                        </span>
                        {lead.lead_score ? (
                          <span className="inline-flex items-center gap-1 rounded-full bg-orange-50 px-2 py-0.5 text-caption font-bold text-orange-700">
                            <Flame className="size-3" />
                            {lead.lead_score}
                          </span>
                        ) : null}
                        <StatusBadge status={lead.lead_status} />
                      </div>
                      <div className="mt-1 flex flex-wrap items-center gap-2 text-caption text-gray-500">
                        {lead.city || lead.country ? (
                          <span className="inline-flex items-center gap-1">
                            <MapPin className="size-3" />
                            {[lead.city, lead.country].filter(Boolean).join(", ")}
                          </span>
                        ) : null}
                        {lead.website_url ? (
                          <span className="inline-flex items-center gap-1 truncate max-w-xs">
                            <Globe className="size-3" />
                            {lead.website_url.replace(/^https?:\/\//, "")}
                          </span>
                        ) : null}
                        {lead.industry ? <span>• {lead.industry}</span> : null}
                      </div>
                    </div>
                    <ArrowRight className="size-4 shrink-0 text-gray-300 group-hover:text-primary-600 transition-transform group-hover:translate-x-0.5" />
                  </button>
                ))}
              </div>
            </div>
          ) : null}

          {/* Matching Mockups */}
          {mockups.length > 0 ? (
            <div>
              <p className="px-3 py-1.5 text-caption font-semibold uppercase tracking-wider text-gray-400">
                Mockups ({mockups.length})
              </p>
              <div className="mt-1 space-y-1">
                {mockups.map((mockup) => (
                  <button
                    key={mockup.id}
                    type="button"
                    onClick={() => {
                      onClose();
                      navigate(`/mockups`);
                    }}
                    className="flex w-full items-center justify-between gap-3 rounded-xl px-3 py-2 text-left hover:bg-gray-50 group"
                  >
                    <div className="flex items-center gap-2 min-w-0">
                      <Images className="size-4 text-purple-600 shrink-0" />
                      <span className="font-medium text-ink group-hover:text-primary-700 truncate">
                        {mockup.business_name} — {mockup.title || mockup.design_guide_name || "Concept"}
                      </span>
                    </div>
                    <StatusBadge status={mockup.status} />
                  </button>
                ))}
              </div>
            </div>
          ) : null}

          {/* Quick Navigation Commands */}
          <div>
            <p className="px-3 py-1.5 text-caption font-semibold uppercase tracking-wider text-gray-400">
              Quick Actions & Destinations
            </p>
            <div className="mt-1 grid sm:grid-cols-2 gap-1">
              {quickNavItems.map((item) => {
                const Icon = item.icon;
                return (
                  <button
                    key={item.to}
                    type="button"
                    onClick={() => {
                      onClose();
                      navigate(item.to);
                    }}
                    className="flex items-center justify-between gap-2 rounded-xl px-3 py-2 text-left hover:bg-gray-50 group"
                  >
                    <div className="flex items-center gap-2.5 min-w-0">
                      <Icon className="size-4 text-gray-500 group-hover:text-primary-600 shrink-0" />
                      <span className="text-small font-medium text-ink group-hover:text-primary-700 truncate">
                        {item.label}
                      </span>
                    </div>
                    <span className="rounded bg-gray-100 px-1.5 py-0.5 text-[10px] font-semibold text-gray-500 uppercase tracking-wider">
                      {item.badge}
                    </span>
                  </button>
                );
              })}
            </div>
          </div>
        </div>

        {/* Footer shortcuts */}
        <div className="flex items-center justify-between border-t border-gray-100 bg-gray-50 px-4 py-2 text-caption text-gray-500">
          <div className="flex items-center gap-3">
            <span>Navigation: <kbd className="font-semibold text-gray-600">↑</kbd> <kbd className="font-semibold text-gray-600">↓</kbd></span>
            <span>Select: <kbd className="font-semibold text-gray-600">↵</kbd></span>
          </div>
          <span>Client Acquisition OS</span>
        </div>
      </div>
    </div>
  );
}

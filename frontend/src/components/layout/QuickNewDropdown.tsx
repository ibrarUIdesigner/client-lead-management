import { useState, useRef, useEffect } from "react";
import { useNavigate } from "react-router-dom";
import {
  CalendarClock,
  Compass,
  FileSpreadsheet,
  Images,
  Mail,
  Plus,
  UserPlus,
} from "lucide-react";

import { Button } from "../ui/Button";

export function QuickNewDropdown() {
  const [open, setOpen] = useState(false);
  const navigate = useNavigate();
  const dropdownRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const handleClickOutside = (e: MouseEvent) => {
      if (dropdownRef.current && !dropdownRef.current.contains(e.target as Node)) {
        setOpen(false);
      }
    };
    if (open) {
      document.addEventListener("mousedown", handleClickOutside);
    }
    return () => document.removeEventListener("mousedown", handleClickOutside);
  }, [open]);

  const actions = [
    {
      label: "Find Leads",
      description: "Search local markets & directories",
      icon: Compass,
      to: "/discover",
    },
    {
      label: "Add Lead",
      description: "Create a single prospect manually",
      icon: UserPlus,
      to: "/leads/new",
    },
    {
      label: "Import Leads",
      description: "Upload a CSV spreadsheet",
      icon: FileSpreadsheet,
      to: "/leads/import",
    },
    {
      label: "Generate Mockup",
      description: "Inspect homepage mockup gallery",
      icon: Images,
      to: "/mockups",
    },
    {
      label: "Create Outreach",
      description: "Prepare and send acquisition pitch",
      icon: Mail,
      to: "/outreach",
    },
    {
      label: "Schedule Follow-up",
      description: "Review today's and upcoming follow-ups",
      icon: CalendarClock,
      to: "/follow-ups",
    },
  ];

  return (
    <div className="relative inline-block text-left" ref={dropdownRef}>
      <Button
        variant="primary"
        className="h-8 gap-1.5 px-3 text-small font-medium shadow-xs"
        onClick={() => setOpen((prev) => !prev)}
        aria-expanded={open}
        aria-haspopup="true"
      >
        <Plus className="size-4" />
        <span>New</span>
      </Button>

      {open ? (
        <div className="absolute right-0 z-30 mt-2 w-64 origin-top-right rounded-xl border border-gray-200 bg-white p-1.5 shadow-xl ring-1 ring-black/5 animate-in fade-in zoom-in-95 duration-100">
          <div className="px-2.5 py-1.5 text-caption font-semibold uppercase tracking-wider text-gray-400">
            Quick Actions
          </div>
          <div className="space-y-0.5">
            {actions.map((item) => {
              const Icon = item.icon;
              return (
                <button
                  key={item.label}
                  type="button"
                  onClick={() => {
                    setOpen(false);
                    navigate(item.to);
                  }}
                  className="flex w-full items-start gap-2.5 rounded-lg px-2.5 py-2 text-left hover:bg-gray-50 transition-colors group"
                >
                  <div className="mt-0.5 flex size-6 shrink-0 items-center justify-center rounded-md bg-primary-50 text-primary-600 group-hover:bg-primary-600 group-hover:text-white transition-colors">
                    <Icon className="size-3.5" />
                  </div>
                  <div>
                    <div className="text-small font-semibold text-ink group-hover:text-primary-700">
                      {item.label}
                    </div>
                    <div className="text-[11px] text-gray-500 leading-tight">
                      {item.description}
                    </div>
                  </div>
                </button>
              );
            })}
          </div>
        </div>
      ) : null}
    </div>
  );
}

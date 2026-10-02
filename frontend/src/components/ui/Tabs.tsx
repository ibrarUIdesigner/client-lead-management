import { useId, useState, type ReactNode } from "react";

import { cn, focusRing } from "../../lib/cn";

export type TabItem = {
  id: string;
  label: string;
  content: ReactNode;
  count?: number;
};

type TabsProps = {
  label: string;
  tabs: TabItem[];
  value?: string;
  onValueChange?: (id: string) => void;
};

export function Tabs({ label, tabs, value, onValueChange }: TabsProps) {
  const baseId = useId();
  const [uncontrolledId, setUncontrolledId] = useState(tabs[0]?.id ?? "");
  const activeId = value ?? uncontrolledId;
  const activeTab = tabs.find((tab) => tab.id === activeId) ?? tabs[0];

  const selectTab = (tabId: string) => {
    if (value === undefined) {
      setUncontrolledId(tabId);
    }
    onValueChange?.(tabId);
    document.getElementById(`${baseId}-${tabId}`)?.focus();
  };

  return (
    <div>
      <div
        role="tablist"
        aria-label={label}
        className="flex gap-1 overflow-x-auto rounded-card bg-gray-100 p-1 [scrollbar-width:thin]"
      >
        {tabs.map((tab) => {
          const selected = tab.id === activeTab?.id;

          return (
            <button
              key={tab.id}
              type="button"
              role="tab"
              id={`${baseId}-${tab.id}`}
              aria-selected={selected}
              aria-controls={`${baseId}-panel-${tab.id}`}
              tabIndex={selected ? 0 : -1}
              className={cn(
                "inline-flex min-h-10 shrink-0 items-center gap-2 rounded-control px-3 text-body font-medium whitespace-nowrap",
                focusRing,
                selected ? "bg-white text-ink shadow-sm" : "text-gray-600 hover:text-ink",
              )}
              onClick={() => {
                selectTab(tab.id);
              }}
              onKeyDown={(event) => {
                const index = tabs.findIndex((item) => item.id === tab.id);
                if (event.key !== "ArrowRight" && event.key !== "ArrowLeft") {
                  return;
                }

                event.preventDefault();
                const nextIndex =
                  event.key === "ArrowRight"
                    ? (index + 1) % tabs.length
                    : (index - 1 + tabs.length) % tabs.length;
                selectTab(tabs[nextIndex]?.id ?? tab.id);
              }}
            >
              {tab.label}
              {tab.count !== undefined ? (
                <span
                  className={cn(
                    "rounded-full px-1.5 text-caption font-semibold tabular-nums",
                    selected ? "bg-primary-50 text-primary-700" : "bg-white text-gray-500",
                  )}
                >
                  {tab.count}
                </span>
              ) : null}
            </button>
          );
        })}
      </div>
      {activeTab ? (
        <div
          role="tabpanel"
          id={`${baseId}-panel-${activeTab.id}`}
          aria-labelledby={`${baseId}-${activeTab.id}`}
          className="pt-5"
        >
          {activeTab.content}
        </div>
      ) : null}
    </div>
  );
}

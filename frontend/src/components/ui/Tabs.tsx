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
        className="inline-flex max-w-full gap-1 overflow-x-auto rounded-xl border border-gray-200/70 bg-gray-100/80 p-1 [scrollbar-width:none]"
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
                "inline-flex h-9 shrink-0 items-center gap-2 rounded-lg px-3.5 text-small font-medium whitespace-nowrap transition-all duration-150",
                focusRing,
                selected
                  ? "bg-white font-semibold text-ink shadow-2xs"
                  : "text-gray-600 hover:bg-white/60 hover:text-ink",
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
              <span>{tab.label}</span>
              {tab.count !== undefined ? (
                <span
                  className={cn(
                    "rounded-full px-1.5 py-0.2 text-[10px] font-bold tabular-nums",
                    selected ? "bg-primary-50 text-primary-700" : "bg-gray-200/80 text-gray-600",
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

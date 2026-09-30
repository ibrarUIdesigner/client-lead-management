import { useId, useState, type ReactNode } from "react";

import { cn, focusRing } from "../../lib/cn";

export type TabItem = {
  id: string;
  label: string;
  content: ReactNode;
};

type TabsProps = {
  label: string;
  tabs: TabItem[];
};

export function Tabs({ label, tabs }: TabsProps) {
  const baseId = useId();
  const [activeId, setActiveId] = useState(tabs[0]?.id ?? "");
  const activeTab = tabs.find((tab) => tab.id === activeId) ?? tabs[0];

  const selectTab = (tabId: string) => {
    setActiveId(tabId);
    document.getElementById(`${baseId}-${tabId}`)?.focus();
  };

  return (
    <div>
      <div role="tablist" aria-label={label} className="flex gap-1 border-b border-gray-200">
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
                "min-h-11 border-b-2 px-3 text-body font-medium",
                focusRing,
                selected ? "border-primary text-primary-700" : "border-transparent text-gray-500",
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
            </button>
          );
        })}
      </div>
      {activeTab ? (
        <div
          role="tabpanel"
          id={`${baseId}-panel-${activeTab.id}`}
          aria-labelledby={`${baseId}-${activeTab.id}`}
          className="pt-4"
        >
          {activeTab.content}
        </div>
      ) : null}
    </div>
  );
}

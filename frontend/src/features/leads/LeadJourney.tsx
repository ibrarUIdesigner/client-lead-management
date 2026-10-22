import {
  Check,
  ChevronRight,
  Sparkles,
} from "lucide-react";
import { cn } from "../../lib/cn";
import type { JourneyStep } from "../../lib/leadWorkflow";

type LeadJourneyProps = {
  steps: JourneyStep[];
  onSelectTab?: (tabId: string) => void;
  className?: string;
};

export function LeadJourney({ steps, onSelectTab, className }: LeadJourneyProps) {
  return (
    <div
      className={cn(
        "rounded-card border border-gray-200 bg-white p-3.5 shadow-2xs",
        className,
      )}
    >
      <div className="flex items-center justify-between gap-2 px-1 pb-2.5">
        <div className="flex items-center gap-1.5">
          <Sparkles className="size-4 text-primary-600" />
          <span className="text-caption font-semibold tracking-wide uppercase text-gray-500">
            Acquisition Lifecycle Journey
          </span>
        </div>
        <span className="text-caption text-gray-400">
          Click any step to inspect or execute
        </span>
      </div>

      <ol className="flex items-center gap-1 overflow-x-auto py-1 scrollbar-none">
        {steps.map((step, idx) => {
          const isCompleted = step.status === "completed";
          const isCurrent = step.status === "current";
          const isClickable = Boolean(step.tabId && onSelectTab);

          return (
            <li
              key={step.id}
              className="flex items-center shrink-0"
            >
              <button
                type="button"
                disabled={!isClickable}
                onClick={() => {
                  if (step.tabId && onSelectTab) {
                    onSelectTab(step.tabId);
                  }
                }}
                className={cn(
                  "group flex items-center gap-2 rounded-control px-2.5 py-1.5 text-left transition-all",
                  isClickable && "hover:bg-gray-50 cursor-pointer",
                  !isClickable && "cursor-default",
                  isCurrent && "bg-primary-50/80 ring-1 ring-primary-200",
                )}
                title={step.description}
              >
                <div
                  className={cn(
                    "flex size-6 shrink-0 items-center justify-center rounded-full text-caption font-semibold transition-colors",
                    isCompleted && "bg-emerald-600 text-white",
                    isCurrent && "bg-primary-600 text-white ring-2 ring-primary-200 ring-offset-1 animate-pulse",
                    step.status === "upcoming" && "border border-gray-300 bg-gray-50 text-gray-400",
                  )}
                >
                  {isCompleted ? (
                    <Check className="size-3.5 stroke-[3]" />
                  ) : (
                    <span>{idx + 1}</span>
                  )}
                </div>

                <div className="flex flex-col min-w-0 pr-1">
                  <span
                    className={cn(
                      "text-caption font-semibold leading-tight",
                      isCompleted && "text-gray-900",
                      isCurrent && "text-primary-900 font-bold",
                      step.status === "upcoming" && "text-gray-400",
                    )}
                  >
                    {step.label}
                  </span>
                  <span
                    className={cn(
                      "truncate text-[11px] leading-tight",
                      isCurrent ? "text-primary-700 font-medium" : "text-gray-500",
                    )}
                  >
                    {step.description}
                  </span>
                </div>
              </button>

              {idx < steps.length - 1 ? (
                <ChevronRight className="size-3.5 shrink-0 text-gray-300 mx-0.5" />
              ) : null}
            </li>
          );
        })}
      </ol>
    </div>
  );
}

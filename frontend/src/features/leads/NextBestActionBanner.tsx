import {
  ArrowRight,
  Flame,
  Lightbulb,
  Sparkles,
} from "lucide-react";
import { Badge } from "../../components/ui/Badge";
import { Button } from "../../components/ui/Button";
import { cn } from "../../lib/cn";
import type { NextBestAction } from "../../lib/leadWorkflow";

type NextBestActionBannerProps = {
  action: NextBestAction;
  onExecute?: () => void;
  className?: string;
  compact?: boolean;
};

export function NextBestActionBanner({
  action,
  onExecute,
  className,
  compact = false,
}: NextBestActionBannerProps) {
  const isHighPriority = action.priority === "critical" || action.priority === "high";

  if (compact) {
    return (
      <div
        className={cn(
          "flex items-center justify-between gap-3 rounded-control border px-3 py-2 text-small",
          isHighPriority
            ? "border-primary-200 bg-primary-50/70 text-primary-950"
            : "border-gray-200 bg-gray-50 text-gray-800",
          className,
        )}
      >
        <div className="flex items-center gap-2 min-w-0">
          {isHighPriority ? (
            <Flame className="size-4 shrink-0 text-orange-600" />
          ) : (
            <Lightbulb className="size-4 shrink-0 text-primary-600" />
          )}
          <div className="truncate">
            <span className="font-semibold">{action.action}</span>
            <span className="text-gray-500 ml-2 hidden sm:inline text-caption">
              {action.reason}
            </span>
          </div>
        </div>

        {onExecute ? (
          <Button
            variant={isHighPriority ? "primary" : "secondary"}
            className="shrink-0 h-7 text-caption px-2.5 font-medium"
            onClick={onExecute}
          >
            {action.ctaLabel}
          </Button>
        ) : null}
      </div>
    );
  }

  return (
    <div
      className={cn(
        "relative overflow-hidden rounded-card border transition-all shadow-sm",
        isHighPriority
          ? "border-primary-300 bg-gradient-to-r from-primary-50/90 via-indigo-50/50 to-white"
          : "border-gray-200 bg-gradient-to-r from-gray-50 to-white",
        className,
      )}
    >
      <div className="flex flex-col gap-4 p-4 sm:flex-row sm:items-center sm:justify-between sm:p-5">
        <div className="flex items-start gap-3.5">
          <div
            className={cn(
              "flex size-10 shrink-0 items-center justify-center rounded-xl shadow-xs",
              isHighPriority
                ? "bg-primary-600 text-white"
                : "bg-gray-100 text-gray-700",
            )}
          >
            {isHighPriority ? (
              <Sparkles className="size-5" />
            ) : (
              <Lightbulb className="size-5" />
            )}
          </div>

          <div className="space-y-1">
            <div className="flex flex-wrap items-center gap-2">
              <span className="text-caption font-bold tracking-wider uppercase text-primary-700">
                Next Best Action
              </span>
              <Badge
                tone={
                  action.tone === "warning"
                    ? "orange"
                    : action.tone === "success"
                    ? "green"
                    : "blue"
                }
              >
                {action.badge}
              </Badge>
            </div>
            <h3 className="text-h4 font-bold text-ink">{action.action}</h3>
            <p className="max-w-2xl text-small text-gray-600 leading-relaxed">
              {action.reason}
            </p>
          </div>
        </div>

        {onExecute ? (
          <div className="shrink-0 sm:self-center">
            <Button
              variant={isHighPriority ? "primary" : "secondary"}
              className="w-full sm:w-auto shadow-xs font-semibold gap-2 h-9 px-4 text-small"
              onClick={onExecute}
            >
              <span>{action.ctaLabel}</span>
              <ArrowRight className="size-4" />
            </Button>
          </div>
        ) : null}
      </div>
    </div>
  );
}

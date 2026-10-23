import { useState } from "react";
import { Link } from "react-router-dom";
import { CalendarClock, Flame, Globe, Zap } from "lucide-react";

import { Button } from "../../components/ui/Button";
import { Select } from "../../components/ui/Select";
import { cn, focusRing } from "../../lib/cn";
import { formatWhen } from "../../lib/format";
import type { Lead } from "../../types/lead";
import { leadStatusOptions, type LeadStatus } from "./statuses";

const CORE_STAGES: LeadStatus[] = [
  "NEW",
  "QUALIFIED",
  "AUDIT_COMPLETE",
  "MOCKUP_READY",
  "CONTACTED",
  "FOLLOW_UP",
  "REPLIED",
  "MEETING",
  "PROPOSAL",
  "WON",
];

type PipelineBoardProps = {
  leads: Lead[];
  pendingId: string | null;
  onMove: (id: string, status: string) => void;
};

export function PipelineBoard({ leads, pendingId, onMove }: PipelineBoardProps) {
  const [showAllStages, setShowAllStages] = useState(false);
  const [stage, setStage] = useState<string>(leadStatusOptions[0].value);

  const displayedColumns = showAllStages
    ? leadStatusOptions
    : leadStatusOptions.filter((col) => CORE_STAGES.includes(col.value as LeadStatus));

  const mobileColumn =
    leadStatusOptions.find((column) => column.value === stage) ?? leadStatusOptions[0];

  return (
    <>
      <div className="mb-4 flex items-center justify-between">
        <div className="flex items-center gap-2">
          <Button
            size="sm"
            variant={showAllStages ? "secondary" : "primary"}
            onClick={() => setShowAllStages(false)}
          >
            Core Stages ({CORE_STAGES.length})
          </Button>
          <Button
            size="sm"
            variant={showAllStages ? "primary" : "secondary"}
            onClick={() => setShowAllStages(true)}
          >
            All Stages ({leadStatusOptions.length})
          </Button>
        </div>
        <p className="text-caption text-gray-500 hidden sm:block">
          {showAllStages
            ? "Showing all statuses including pending and closed"
            : "Showing active prospect progression stages"}
        </p>
      </div>

      <div className="md:hidden">
        <Select
          label="Pipeline Stage"
          options={displayedColumns}
          value={stage}
          onChange={(event) => {
            setStage(event.target.value);
          }}
        />
        <div className="mt-4">
          <StageColumn
            status={mobileColumn.value}
            label={mobileColumn.label}
            leads={leads.filter((lead) => lead.lead_status === mobileColumn.value)}
            pendingId={pendingId}
            onMove={onMove}
            stacked
          />
        </div>
      </div>
      <div className="hidden gap-4 overflow-x-auto pb-4 md:flex">
        {displayedColumns.map((column) => (
          <StageColumn
            key={column.value}
            status={column.value}
            label={column.label}
            leads={leads.filter((lead) => lead.lead_status === column.value)}
            pendingId={pendingId}
            onMove={onMove}
          />
        ))}
      </div>
    </>
  );
}

type StageColumnProps = {
  status: LeadStatus;
  label: string;
  leads: Lead[];
  pendingId: string | null;
  onMove: (id: string, status: string) => void;
  stacked?: boolean;
};

function StageColumn({
  status,
  label,
  leads,
  pendingId,
  onMove,
  stacked = false,
}: StageColumnProps) {
  return (
    <section
      aria-label={label}
      className={cn(
        "flex flex-col rounded-card border border-gray-200 bg-gray-50/70",
        stacked ? "w-full" : "w-[280px] shrink-0",
      )}
      onDragOver={(event) => {
        event.preventDefault();
      }}
      onDrop={(event) => {
        event.preventDefault();
        const id = event.dataTransfer.getData("text/plain");
        if (id) {
          onMove(id, status);
        }
      }}
    >
      <header className="flex items-center justify-between border-b border-gray-200/80 px-3.5 py-3 bg-white rounded-t-card">
        <h2 className="text-small font-bold text-ink">{label}</h2>
        <span className="rounded-full bg-gray-100 px-2 py-0.5 text-caption font-bold text-gray-600 ring-1 ring-inset ring-gray-400/15">
          {leads.length}
        </span>
      </header>
      <div className="flex flex-1 flex-col gap-2.5 p-2.5">
        {leads.length === 0 ? (
          <p className="rounded-control border border-dashed border-gray-200 px-3 py-6 text-center text-caption text-gray-400">
            No prospects in this stage.
          </p>
        ) : (
          leads.map((lead) => (
            <article
              key={lead.id}
              draggable
              onDragStart={(event) => {
                event.dataTransfer.effectAllowed = "move";
                event.dataTransfer.setData("text/plain", lead.id);
              }}
              className="rounded-control border border-gray-200/90 bg-white p-3 shadow-2xs hover:border-gray-300 hover:shadow-xs transition-all cursor-grab active:cursor-grabbing"
            >
              <div className="flex items-start justify-between gap-2">
                <Link
                  to={`/leads/${lead.id}`}
                  className={cn("font-bold text-ink hover:text-primary-700 truncate", focusRing)}
                >
                  {lead.business_name}
                </Link>
                {lead.lead_score !== null && lead.lead_score !== undefined ? (
                  <span
                    className={cn(
                      "shrink-0 inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-[11px] font-bold shadow-2xs",
                      lead.lead_score >= 70
                        ? "bg-amber-100 text-amber-900 border border-amber-200"
                        : lead.lead_score >= 40
                          ? "bg-blue-50 text-blue-800 border border-blue-200"
                          : "bg-gray-100 text-gray-700 border border-gray-200",
                    )}
                    title={`Opportunity Score: ${lead.lead_score}/100`}
                  >
                    {lead.lead_score >= 70 ? (
                      <>
                        <Flame className="size-3 text-amber-600 fill-amber-500" />
                        <span>{lead.lead_score} High</span>
                      </>
                    ) : lead.lead_score >= 40 ? (
                      <>
                        <Zap className="size-3 text-blue-600 fill-blue-500" />
                        <span>{lead.lead_score} Med</span>
                      </>
                    ) : (
                      <span>{lead.lead_score} Low</span>
                    )}
                  </span>
                ) : null}
              </div>

              <p className="mt-0.5 text-caption text-gray-500">
                {[lead.industry, lead.city].filter(Boolean).join(" · ") || "Local Business"}
              </p>

              <div className="mt-2 flex flex-wrap items-center gap-1.5 text-[11px]">
                {lead.website_url ? (
                  <span className="inline-flex items-center gap-1 rounded bg-gray-100 px-1.5 py-0.5 text-gray-600">
                    <Globe className="size-3" />
                    {lead.website_quality_score ? `Quality ${lead.website_quality_score}` : "Website"}
                  </span>
                ) : (
                  <span className="rounded bg-amber-50 px-1.5 py-0.5 font-medium text-amber-800">
                    No Website
                  </span>
                )}

                {lead.next_followup_at ? (
                  <span className="inline-flex items-center gap-1 rounded bg-blue-50 px-1.5 py-0.5 text-blue-700">
                    <CalendarClock className="size-3" />
                    {formatWhen(lead.next_followup_at)}
                  </span>
                ) : null}
              </div>

              <div className="mt-2.5 pt-2 border-t border-gray-100">
                <Select
                  label={`Move ${lead.business_name}`}
                  options={leadStatusOptions}
                  value={lead.lead_status}
                  disabled={pendingId === lead.id}
                  onChange={(event) => {
                    onMove(lead.id, event.target.value);
                  }}
                />
              </div>
            </article>
          ))
        )}
      </div>
    </section>
  );
}

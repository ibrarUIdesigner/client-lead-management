import { useState } from "react";
import { Link } from "react-router-dom";

import { Select } from "../../components/ui/Select";
import { cn, focusRing } from "../../lib/cn";
import type { Lead } from "../../types/lead";
import { leadStatusOptions, type LeadStatus } from "./statuses";

type PipelineBoardProps = {
  leads: Lead[];
  pendingId: string | null;
  onMove: (id: string, status: string) => void;
};

export function PipelineBoard({ leads, pendingId, onMove }: PipelineBoardProps) {
  const [stage, setStage] = useState<string>(leadStatusOptions[0].value);
  const mobileColumn =
    leadStatusOptions.find((column) => column.value === stage) ?? leadStatusOptions[0];

  return (
    <>
      <div className="md:hidden">
        <Select
          label="Stage"
          options={leadStatusOptions}
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
        {leadStatusOptions.map((column) => (
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
        "flex flex-col rounded-card border border-gray-200 bg-gray-50",
        stacked ? "w-full" : "w-[260px] shrink-0",
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
      <header className="flex items-center justify-between px-3 py-3">
        <h2 className="text-small font-semibold text-ink">{label}</h2>
        <span className="text-caption text-gray-500">{leads.length}</span>
      </header>
      <div className="flex flex-1 flex-col gap-2 px-3 pb-3">
        {leads.length === 0 ? (
          <p className="rounded-control border border-dashed border-gray-300 px-3 py-6 text-small text-gray-500">
            No leads in this stage.
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
              className="rounded-control border border-gray-200 bg-white p-3"
            >
              <Link
                to={`/leads/${lead.id}`}
                className={cn("font-semibold text-ink hover:text-primary-700", focusRing)}
              >
                {lead.business_name}
              </Link>
              {lead.city ? <p className="mt-1 text-small text-gray-600">{lead.city}</p> : null}
              <div className="mt-3">
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

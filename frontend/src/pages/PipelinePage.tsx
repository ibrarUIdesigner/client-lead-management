import { useState } from "react";
import { useQueryClient } from "@tanstack/react-query";

import { useToast } from "../components/feedback/useToast";
import { PageHeader } from "../components/layout/PageHeader";
import { Button } from "../components/ui/Button";
import { Skeleton } from "../components/ui/Skeleton";
import { PipelineBoard } from "../features/leads/PipelineBoard";
import { useLeads, useUpdateLeadStatus } from "../hooks/useLeads";
import { apiErrorMessage } from "../lib/apiError";
import type { LeadPage } from "../types/lead";

export function PipelinePage() {
  const { notify } = useToast();
  const queryClient = useQueryClient();
  const [limit, setLimit] = useState(100);
  const pipelineParams = {
    limit,
    sort: "updated_at",
    direction: "desc",
  } as const;

  const leads = useLeads(pipelineParams);
  const updateStatus = useUpdateLeadStatus();
  const [pendingId, setPendingId] = useState<string | null>(null);
  const queryKey = ["leads", pipelineParams] as const;

  const moveLead = (id: string, status: string) => {
    const current = leads.data?.items.find((lead) => lead.id === id);
    if (!current || current.lead_status === status || pendingId) {
      return;
    }

    const previous = queryClient.getQueryData<LeadPage>(queryKey);
    queryClient.setQueryData<LeadPage>(queryKey, (data) => {
      if (!data) {
        return data;
      }
      return {
        ...data,
        items: data.items.map((lead) => (lead.id === id ? { ...lead, lead_status: status } : lead)),
      };
    });
    setPendingId(id);
    updateStatus.mutate(
      { id, leadStatus: status },
      {
        onError: () => {
          if (previous) {
            queryClient.setQueryData(queryKey, previous);
          }
          notify("Could not move that lead. It was put back.", "danger");
        },
        onSettled: () => {
          setPendingId(null);
        },
      },
    );
  };

  return (
    <>
      <PageHeader
        title="Pipeline"
        description="Move a lead by dragging it on a wide screen, or choose a stage on the card."
      />
      {leads.isPending ? (
        <div className="space-y-3" aria-busy="true">
          <Skeleton className="h-8 w-40" />
          <Skeleton className="h-64 w-full" />
        </div>
      ) : null}
      {leads.isError ? (
        <div className="flex flex-col items-start gap-3" role="alert">
          <p className="text-body text-danger">
            {apiErrorMessage(leads.error, "The pipeline could not be loaded.")}
          </p>
          <Button
            variant="secondary"
            onClick={() => {
              void leads.refetch();
            }}
          >
            Retry
          </Button>
        </div>
      ) : null}
      {leads.data ? (
        <>
          <div className="mb-4 flex flex-wrap items-center justify-between gap-3">
            <p className="text-small text-gray-500">
              Showing {leads.data.items.length} of {leads.data.total} leads.
            </p>
            {leads.data.has_next ? (
              <Button
                variant="secondary"
                size="sm"
                isLoading={leads.isFetching}
                onClick={() => setLimit((prev) => prev + 100)}
              >
                Load more leads (+100)
              </Button>
            ) : null}
          </div>
          <PipelineBoard leads={leads.data.items} pendingId={pendingId} onMove={moveLead} />
        </>
      ) : null}
    </>
  );
}

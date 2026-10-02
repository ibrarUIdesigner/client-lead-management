import { useState } from "react";
import { Bot, Plus } from "lucide-react";

import { DataTable, type DataColumn } from "../components/data/DataTable";
import { EmptyState } from "../components/feedback/EmptyState";
import { QueryGate } from "../components/feedback/QueryGate";
import { useToast } from "../components/feedback/useToast";
import { PageHeader } from "../components/layout/PageHeader";
import { StatusBadge } from "../components/ui/Badge";
import { Button } from "../components/ui/Button";
import { Card } from "../components/ui/Card";
import { ConfirmDialog } from "../components/ui/ConfirmDialog";
import { Spinner } from "../components/ui/Spinner";
import { Tabs } from "../components/ui/Tabs";
import { AddConnectorDialog } from "../features/apify/AddConnectorDialog";
import { ResultsPanel } from "../features/apify/ResultsPanel";
import { RunActorDialog } from "../features/apify/RunActorDialog";
import { useAbortApifyRun, useApify, useDeleteApifyConnector } from "../hooks/useApify";
import { apiErrorMessage } from "../lib/apiError";
import { formatWhen } from "../lib/format";
import { ACTIVE_RUN_STATUSES, type ApifyConnector, type ApifyRun } from "../types/apify";

export function ApifyPage() {
  const apify = useApify();
  const [addOpen, setAddOpen] = useState(false);
  const [tab, setTab] = useState("connectors");
  const [runTarget, setRunTarget] = useState<ApifyConnector | null>(null);
  const [selectedRunId, setSelectedRunId] = useState<string | null>(null);
  const { notify } = useToast();

  const runs = apify.data?.runs ?? [];
  const activeRun = runs.find((run) => ACTIVE_RUN_STATUSES.has(run.status)) ?? null;
  const [trackedActiveId, setTrackedActiveId] = useState<string | null>(null);
  if (activeRun && activeRun.id !== trackedActiveId && selectedRunId == null) {
    setTrackedActiveId(activeRun.id);
    setSelectedRunId(activeRun.id);
    setTab("history");
  }
  const selectedRun = runs.find((run) => run.id === selectedRunId) ?? null;

  return (
    <>
      <PageHeader
        title="Apify"
        description="Actors from your Apify account are listed here. Run one with your own filters, then import the records you want as leads."
        actions={
          <Button
            onClick={() => {
              setAddOpen(true);
            }}
          >
            <Plus size={18} aria-hidden="true" />
            Add connector
          </Button>
        }
      />
      <QueryGate
        pending={apify.isPending}
        error={apify.error}
        fallback="Apify could not be loaded."
        onRetry={() => {
          void apify.refetch();
        }}
      >
        {apify.data ? (
          <Tabs
            label="Apify"
            value={tab}
            onValueChange={setTab}
            tabs={[
              {
                id: "connectors",
                label: "Connectors",
                count: apify.data.connectors.length,
                content: (
                  <div className="space-y-4">
                    {!apify.data.token_configured ? (
                      <p
                        className="rounded-card border border-amber-200 bg-amber-50 px-4 py-3 text-body text-amber-950"
                        role="status"
                      >
                        Set APIFY_TOKEN on the server before connecting actors. The token stays on
                        the server and is not stored in the browser.
                      </p>
                    ) : null}
                    {apify.data.token_error ? (
                      <p className="text-body text-danger" role="alert">
                        {apify.data.token_error}
                      </p>
                    ) : null}
                    {apify.data.connectors.length === 0 ? (
                      <EmptyState
                        title="No actors yet"
                        description="Actors you have created or used in Apify show up here. You can also add one by its ID or owner/name."
                        action={
                          <Button
                            onClick={() => {
                              setAddOpen(true);
                            }}
                          >
                            Add connector
                          </Button>
                        }
                      />
                    ) : (
                      <div className="grid gap-4">
                        {apify.data.connectors.map((connector) => (
                          <ConnectorCard
                            key={connector.id}
                            connector={connector}
                            tokenConfigured={apify.data?.token_configured ?? false}
                            onRun={() => {
                              setRunTarget(connector);
                            }}
                            onRemoved={() => {
                              if (selectedRun?.connector_id === connector.id) {
                                setSelectedRunId(null);
                              }
                              notify("Connector removed.");
                            }}
                          />
                        ))}
                      </div>
                    )}
                  </div>
                ),
              },
              {
                id: "history",
                label: "Run history",
                count: runs.length,
                content: (
                  <div className="space-y-6">
                    {selectedRun ? (
                      <section id="run-progress" className="space-y-4" aria-labelledby="run-progress-title">
                        <RunProgress
                          run={selectedRun}
                          onAbortError={(message) => {
                            notify(message, "danger");
                          }}
                        />
                        <ResultsPanel
                          key={selectedRun.id}
                          run={selectedRun}
                          onImported={(message) => {
                            notify(message, "success");
                          }}
                        />
                      </section>
                    ) : null}
                    <DataTable
                      columns={historyColumns(selectedRunId, (runId) => {
                        setSelectedRunId(runId);
                        window.setTimeout(() => {
                          document.getElementById("run-progress")?.scrollIntoView({ behavior: "smooth" });
                        }, 50);
                      })}
                      rows={runs}
                      getRowId={(run) => run.id}
                      emptyTitle="No runs yet"
                      emptyDescription="Runs will show up here after you start an actor."
                    />
                  </div>
                ),
              },
            ]}
          />
        ) : null}
      </QueryGate>
      {addOpen ? (
        <AddConnectorDialog
          open
          onClose={() => {
            setAddOpen(false);
          }}
        />
      ) : null}
      {runTarget ? (
        <RunActorDialog
          connector={runTarget}
          open
          onClose={() => {
            setRunTarget(null);
          }}
          onStarted={(runId) => {
            setSelectedRunId(runId);
            setTab("history");
            notify("Actor run started.");
            window.setTimeout(() => {
              document.getElementById("run-progress")?.scrollIntoView({ behavior: "smooth" });
            }, 50);
          }}
        />
      ) : null}
    </>
  );
}

function ConnectorCard({
  connector,
  tokenConfigured,
  onRun,
  onRemoved,
}: {
  connector: ApifyConnector;
  tokenConfigured: boolean;
  onRun: () => void;
  onRemoved: () => void;
}) {
  const remove = useDeleteApifyConnector();
  const [confirming, setConfirming] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function onRemove() {
    setError(null);
    try {
      await remove.mutateAsync(connector.id);
      setConfirming(false);
      onRemoved();
    } catch (caught) {
      setError(apiErrorMessage(caught, "That connector could not be removed."));
    }
  }

  return (
    <Card>
      <div className="flex flex-col gap-4 lg:flex-row lg:items-start lg:justify-between">
        <div className="min-w-0">
          <div className="flex flex-wrap items-center gap-2">
            <Bot size={18} aria-hidden="true" className="text-primary-700" />
            <h2 className="text-h4 font-semibold text-ink">{connector.display_name}</h2>
            <span className="rounded-control bg-gray-100 px-2 py-1 text-caption font-medium text-gray-700">
              {connector.source}
            </span>
          </div>
          <p className="mt-2 max-w-3xl text-body text-gray-600">
            {connector.description || "No description was published for this actor."}
          </p>
          <p className="mt-3 text-small text-gray-600">
            Actor ID <span className="font-medium text-ink">{connector.actor_id}</span>
          </p>
          <p className="mt-1 text-small text-gray-600">
            Last run{" "}
            {connector.last_run_at ? (
              <>
                <span className="text-ink">{formatWhen(connector.last_run_at)}</span>
                {connector.last_run_status ? (
                  <span className="ml-2 inline-flex align-middle">
                    <StatusBadge status={connector.last_run_status} />
                  </span>
                ) : null}
              </>
            ) : (
              <span className="text-ink">No runs yet</span>
            )}
          </p>
          {connector.has_active_run ? (
            <p className="mt-2 text-small text-gray-600">A run is already in progress.</p>
          ) : null}
          {error ? (
            <p className="mt-2 text-small text-danger" role="alert">
              {error}
            </p>
          ) : null}
        </div>
        <div className="flex flex-col gap-2 sm:flex-row sm:flex-wrap">
          <Button onClick={onRun} disabled={!tokenConfigured || connector.has_active_run}>
            Run Actor
          </Button>
          <Button
            variant="secondary"
            onClick={() => {
              setConfirming(true);
            }}
          >
            Remove
          </Button>
        </div>
      </div>
      <ConfirmDialog
        open={confirming}
        title="Remove this connector?"
        description="Run history for this connector will be removed. Leads already imported will stay."
        confirmLabel="Remove connector"
        isLoading={remove.isPending}
        onConfirm={() => {
          void onRemove();
        }}
        onClose={() => {
          if (!remove.isPending) {
            setConfirming(false);
          }
        }}
      />
    </Card>
  );
}

function RunProgress({
  run,
  onAbortError,
}: {
  run: ApifyRun;
  onAbortError: (message: string) => void;
}) {
  const abort = useAbortApifyRun();
  const [confirming, setConfirming] = useState(false);
  const active = ACTIVE_RUN_STATUSES.has(run.status);

  async function onAbort() {
    try {
      await abort.mutateAsync(run.id);
      setConfirming(false);
    } catch (caught) {
      onAbortError(apiErrorMessage(caught, "The run could not be aborted."));
    }
  }

  return (
    <Card>
      <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
        <div>
          <h2 id="run-progress-title" className="text-h4 font-semibold text-ink">
            {run.connector_name}
          </h2>
          <div className="mt-2 flex flex-wrap items-center gap-2">
            {active ? <Spinner /> : null}
            <StatusBadge status={run.status} />
            <p className="text-small text-gray-600" aria-live="polite">
              {statusCopy(run)}
            </p>
          </div>
          <p className="mt-2 text-small text-gray-600">
            Started {formatWhen(run.started_at)}
            {run.finished_at ? ` · Finished ${formatWhen(run.finished_at)}` : ""}
            {run.result_count != null ? ` · ${run.result_count} results` : ""}
            {run.usage_total_usd != null ? ` · ${formatUsd(run.usage_total_usd)}` : ""}
          </p>
        </div>
        {run.status === "READY" || run.status === "RUNNING" ? (
          <Button
            variant="secondary"
            onClick={() => {
              setConfirming(true);
            }}
          >
            Abort run
          </Button>
        ) : null}
      </div>
      <ConfirmDialog
        open={confirming}
        title="Abort this run?"
        description="The actor stops and any records already collected stay in the run."
        confirmLabel="Abort run"
        isLoading={abort.isPending}
        onConfirm={() => {
          void onAbort();
        }}
        onClose={() => {
          if (!abort.isPending) {
            setConfirming(false);
          }
        }}
      />
    </Card>
  );
}

function historyColumns(
  selectedRunId: string | null,
  onSelect: (runId: string) => void,
): DataColumn<ApifyRun>[] {
  return [
    {
      id: "connector",
      header: "Connector",
      cell: (run) => run.connector_name,
    },
    {
      id: "started",
      header: "Started",
      cell: (run) => formatWhen(run.started_at),
    },
    {
      id: "finished",
      header: "Finished",
      cell: (run) => formatWhen(run.finished_at),
    },
    {
      id: "status",
      header: "Status",
      cell: (run) => <StatusBadge status={run.status} />,
    },
    {
      id: "results",
      header: "Results",
      cell: (run) => (run.result_count == null ? "—" : String(run.result_count)),
    },
    {
      id: "cost",
      header: "Cost",
      cell: (run) => formatUsd(run.usage_total_usd),
    },
    {
      id: "open",
      header: "Records",
      cell: (run) => (
        <Button
          variant="secondary"
          onClick={() => {
            onSelect(run.id);
            document.getElementById("run-progress")?.scrollIntoView({ behavior: "smooth" });
          }}
        >
          {selectedRunId === run.id ? "Viewing" : "View"}
        </Button>
      ),
    },
  ];
}

function statusCopy(run: ApifyRun): string {
  if (run.status_message) {
    return run.status_message;
  }
  if (run.status === "SUCCEEDED") {
    return "The run finished.";
  }
  if (run.status === "FAILED") {
    return "The run failed.";
  }
  if (run.status === "TIMED-OUT") {
    return "The run timed out.";
  }
  if (run.status === "ABORTED") {
    return "The run was aborted.";
  }
  if (run.status === "TIMING-OUT") {
    return "The run is timing out.";
  }
  if (run.status === "ABORTING") {
    return "The run is aborting.";
  }
  if (run.status === "READY") {
    return "The run is starting.";
  }
  return "The run is in progress.";
}

function formatUsd(value: number | null): string {
  if (value == null) {
    return "—";
  }
  return new Intl.NumberFormat(undefined, { style: "currency", currency: "USD" }).format(value);
}

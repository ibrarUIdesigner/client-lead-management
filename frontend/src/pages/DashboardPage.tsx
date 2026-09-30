import { RefreshCw } from "lucide-react";
import axios from "axios";

import { Card } from "../components/ui/Card";
import { EmptyState } from "../components/feedback/EmptyState";
import { PageHeader } from "../components/layout/PageHeader";
import { Badge } from "../components/ui/Badge";
import { Button } from "../components/ui/Button";
import { Skeleton } from "../components/ui/Skeleton";
import { useHealth } from "../hooks/useHealth";
import { isApiErrorBody } from "../types/api";

function errorMessage(error: unknown): string {
  if (axios.isAxiosError(error) && isApiErrorBody(error.response?.data)) {
    return error.response.data.error.message;
  }

  return "The API could not be reached.";
}

export function DashboardPage() {
  const health = useHealth();
  const databaseLabel =
    health.data?.database === "ok" ? "Database connected" : "Database unavailable";

  return (
    <>
      <PageHeader
        title="Dashboard"
        description="What to work on next will collect here as you add leads."
      />
      <div className="grid items-start gap-6 lg:grid-cols-[minmax(0,2fr)_320px]">
        <EmptyState
          title="No work queued"
          description="Leads, audits, and follow-ups will show up here."
        />
        <Card>
          <h2 className="text-h4 font-semibold text-ink">System</h2>
          {health.isPending ? (
            <div className="mt-4 space-y-2" aria-busy="true">
              <Skeleton className="h-6 w-40" />
              <Skeleton className="h-4 w-28" />
            </div>
          ) : null}
          {health.isError ? (
            <div className="mt-4 flex flex-col items-start gap-3" role="alert">
              <p className="text-body text-danger">{errorMessage(health.error)}</p>
              <Button
                variant="secondary"
                onClick={() => {
                  void health.refetch();
                }}
              >
                <RefreshCw size={16} aria-hidden="true" />
                Retry
              </Button>
            </div>
          ) : null}
          {health.data ? (
            <div className="mt-4 flex flex-col items-start gap-3">
              <Badge tone={health.data.database === "ok" ? "green" : "orange"}>
                {databaseLabel}
              </Badge>
              <p className="text-small text-gray-500">Environment: {health.data.environment}</p>
            </div>
          ) : null}
        </Card>
      </div>
    </>
  );
}

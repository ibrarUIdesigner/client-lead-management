import { LoadingState } from "../../components/feedback/LoadingState";
import { useToast } from "../../components/feedback/useToast";
import { Badge, type BadgeTone } from "../../components/ui/Badge";
import { Button } from "../../components/ui/Button";
import { Card } from "../../components/ui/Card";
import { useLeadPipeline, useLeadPipelineActions } from "../../hooks/usePipeline";
import type { PipelineJob } from "../../services/pipeline";

const stepLabels: Record<string, string> = {
  enrich: "Find contact email",
  audit: "Audit website",
  research: "Research business",
  mockup: "Create mockup",
  draft: "Write email draft",
  send: "Send email",
};

const statusTone: Record<PipelineJob["status"], BadgeTone> = {
  QUEUED: "blue",
  RUNNING: "indigo",
  DONE: "green",
  SKIPPED: "gray",
  FAILED: "red",
};

export function LeadPipelinePanel({ leadId }: { leadId: string }) {
  const { notify } = useToast();
  const query = useLeadPipeline(leadId);
  const actions = useLeadPipelineActions(leadId);

  if (query.isPending) return <LoadingState label="Loading automation" />;
  if (query.isError || !query.data) return null;
  const { jobs, paused, next_step: nextStep } = query.data;

  function run(action: "advance" | "pause" | "resume", message: string) {
    actions[action].mutate(undefined, {
      onSuccess: () => notify(message, "success"),
      onError: () => notify("That did not work. Try again.", "danger"),
    });
  }

  return (
    <Card>
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h3 className="text-h4 font-semibold text-ink">Automation</h3>
          <p className="text-small text-gray-600">
            {paused
              ? "Paused. Nothing will run for this lead until you resume."
              : nextStep
                ? `Next: ${stepLabels[nextStep] ?? nextStep}. It runs within about 10 minutes.`
                : "Nothing left to do automatically."}
          </p>
        </div>
        <div className="flex gap-2">
          {paused ? (
            <Button
              variant="secondary"
              size="sm"
              onClick={() => run("resume", "Automation resumed.")}
            >
              Resume
            </Button>
          ) : (
            <>
              <Button
                variant="secondary"
                size="sm"
                disabled={!nextStep}
                onClick={() => run("advance", "Queued. It runs on the next cycle.")}
              >
                Run next step
              </Button>
              <Button variant="ghost" size="sm" onClick={() => run("pause", "Automation paused.")}>
                Pause
              </Button>
            </>
          )}
        </div>
      </div>
      {jobs.length > 0 ? (
        <ul className="mt-4 divide-y divide-gray-100">
          {jobs.map((job) => (
            <li key={job.id} className="flex flex-wrap items-start justify-between gap-2 py-2">
              <div className="min-w-0">
                <p className="text-body text-ink">{stepLabels[job.step] ?? job.step}</p>
                {job.detail || job.last_error ? (
                  <p className="text-small text-gray-600">{job.last_error ?? job.detail}</p>
                ) : null}
              </div>
              <div className="flex items-center gap-2">
                <Badge tone={statusTone[job.status]}>{job.status.toLowerCase()}</Badge>
                {job.status === "FAILED" || job.status === "SKIPPED" ? (
                  <Button
                    variant="ghost"
                    size="sm"
                    onClick={() =>
                      actions.retry.mutate(job.id, {
                        onSuccess: () => notify("Queued again.", "success"),
                        onError: () => notify("Could not retry that step.", "danger"),
                      })
                    }
                  >
                    Retry
                  </Button>
                ) : null}
              </div>
            </li>
          ))}
        </ul>
      ) : null}
    </Card>
  );
}

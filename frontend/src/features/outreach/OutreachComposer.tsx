import { useState } from "react";

import { useToast } from "../../components/feedback/useToast";
import { Button } from "../../components/ui/Button";
import { Card } from "../../components/ui/Card";
import { Select } from "../../components/ui/Select";
import { useLatestAudit } from "../../hooks/useAudit";
import { useGenerateOutreach } from "../../hooks/useOutreach";
import { useOutreachTemplates } from "../../hooks/useWorkspace";
import { apiErrorCode, apiErrorMessage } from "../../lib/apiError";
import { findingLines } from "./findings";

type OutreachComposerProps = {
  leadId: string;
  email: string | null;
  onCreated: (messageId: string) => void;
};

export function OutreachComposer({ leadId, email, onCreated }: OutreachComposerProps) {
  const { notify } = useToast();
  const templates = useOutreachTemplates();
  const audit = useLatestAudit(leadId);
  const generate = useGenerateOutreach(leadId);
  const [templateId, setTemplateId] = useState("");
  const activeTemplates = (templates.data ?? []).filter((item) => item.is_active);
  const missingAudit = audit.isError && apiErrorCode(audit.error) === "AUDIT_NOT_FOUND";
  const running = audit.data?.status === "PENDING" || audit.data?.status === "RUNNING";
  const lines = findingLines(audit.data);

  const createDraft = () => {
    generate.mutate(
      {
        template_id: templateId || undefined,
      },
      {
        onSuccess: (message) => {
          notify("Draft written from the latest audit. Send it from your email app.", "success");
          onCreated(message.id);
        },
        onError: (error) => {
          notify(apiErrorMessage(error, "Could not create the draft."), "danger");
        },
      },
    );
  };

  return (
    <Card>
      <p className="text-caption font-semibold text-gray-500">1. What the email will say</p>
      <h2 className="mt-1 text-h4 font-semibold text-ink">Findings from the latest audit</h2>
      <Findings
        loading={audit.isPending}
        missing={missingAudit}
        running={running}
        failed={audit.data?.status === "FAILED"}
        lines={lines}
      />
      <div className="mt-6 border-t border-gray-200 pt-6">
        <p className="text-caption font-semibold text-gray-500">2. Write the draft</p>
        <p className="mt-1 text-body text-gray-600">
          {email
            ? `This opens in your mail app to ${email}. `
            : "Add an email on this lead before Open in email can be used. "}
          You send it from your own inbox. A draft you already edited stays as you saved it.
        </p>
        {activeTemplates.length > 0 ? (
          <div className="mt-4">
            <Select
              label="Template"
              value={templateId}
              onChange={(event) => {
                setTemplateId(event.target.value);
              }}
              placeholder="Homepage concept"
              options={activeTemplates.map((item) => ({ value: item.id, label: item.name }))}
            />
          </div>
        ) : null}
        <div className="mt-4">
          <Button onClick={createDraft} isLoading={generate.isPending} disabled={running}>
            {lines.length > 0 ? "Write email from these findings" : "Write email"}
          </Button>
        </div>
      </div>
    </Card>
  );
}

function Findings({
  loading,
  missing,
  running,
  failed,
  lines,
}: {
  loading: boolean;
  missing: boolean;
  running: boolean;
  failed: boolean;
  lines: { title: string; detail: string }[];
}) {
  if (loading) {
    return <p className="mt-3 text-body text-gray-600">Loading the latest audit.</p>;
  }
  if (running) {
    return (
      <p className="mt-3 text-body text-gray-600">
        The audit is still running. The email can be written when those findings are ready.
      </p>
    );
  }
  if (missing) {
    return (
      <p className="mt-3 text-body text-gray-600">
        No audit yet. Open the Audit tab and analyze the website, then come back. The email is
        written from those findings.
      </p>
    );
  }
  if (failed) {
    return (
      <p className="mt-3 text-body text-gray-600">
        The last audit did not finish. You can still write a general note, or run the audit again.
      </p>
    );
  }
  if (lines.length === 0) {
    return (
      <p className="mt-3 text-body text-gray-600">
        The latest audit did not list problems. The email will stay general.
      </p>
    );
  }
  return (
    <ul className="mt-4 space-y-3">
      {lines.map((line) => (
        <li key={`${line.title}-${line.detail}`}>
          <p className="font-medium text-ink">{line.title}</p>
          <p className="text-small text-gray-600">{line.detail}</p>
        </li>
      ))}
    </ul>
  );
}

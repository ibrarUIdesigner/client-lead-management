import { useState } from "react";

import { useToast } from "../../components/feedback/useToast";
import { Button } from "../../components/ui/Button";
import { Card } from "../../components/ui/Card";
import { Checkbox } from "../../components/ui/Checkbox";
import { Input } from "../../components/ui/Input";
import { Textarea } from "../../components/ui/Textarea";
import { useLatestAudit } from "../../hooks/useAudit";
import { useGmailStatus, useSendLeadEmail } from "../../hooks/useGmail";
import { useMockups } from "../../hooks/useWorkspace";
import { apiErrorMessage } from "../../lib/apiError";

type GmailComposerProps = {
  leadId: string;
  defaultTo: string | null;
  defaultSubject?: string;
  defaultBody?: string;
  outreachMessageId?: string;
  onSent?: () => void;
};

export function GmailComposer({
  leadId,
  defaultTo,
  defaultSubject = "",
  defaultBody = "",
  outreachMessageId,
  onSent,
}: GmailComposerProps) {
  const { notify } = useToast();
  const gmail = useGmailStatus();
  const send = useSendLeadEmail(leadId);
  const audit = useLatestAudit(leadId);
  const mockups = useMockups(leadId);
  const [to, setTo] = useState(defaultTo ?? "");
  const [subject, setSubject] = useState(defaultSubject);
  const [body, setBody] = useState(defaultBody);
  const [attachAudit, setAttachAudit] = useState(false);
  const [mockupIds, setMockupIds] = useState<string[]>([]);
  const [sending, setSending] = useState(false);

  const connected = Boolean(gmail.data?.connected && !gmail.data.needs_reauth);
  const ready = to.trim().length > 0 && subject.trim().length > 0 && body.trim().length > 0;
  const completedAudit =
    audit.data?.status === "COMPLETED" ? audit.data : null;
  const readyMockups = (mockups.data ?? []).filter((item) => item.status === "READY");

  if (!connected) {
    return (
      <Card>
        <h2 className="text-h4 font-semibold text-ink">Send with Gmail</h2>
        <p className="mt-2 text-body text-gray-600">
          Connect Gmail in Settings to send from this workspace.
        </p>
      </Card>
    );
  }

  const submit = () => {
    if (!ready || sending || send.isPending) {
      return;
    }
    setSending(true);
    const idempotencyKey = crypto.randomUUID();
    send.mutate(
      {
        to: to.trim(),
        subject: subject.trim(),
        body: body.trim(),
        outreach_message_id: outreachMessageId,
        attachment_audit_id: attachAudit && completedAudit ? completedAudit.id : undefined,
        attachment_mockup_ids: mockupIds,
        idempotency_key: idempotencyKey,
      },
      {
        onSuccess: () => {
          notify("Email accepted by Gmail. Delivery is not confirmed yet.", "success");
          onSent?.();
        },
        onError: (error) => {
          notify(apiErrorMessage(error, "Could not send via Gmail."), "danger");
        },
        onSettled: () => {
          setSending(false);
        },
      },
    );
  };

  return (
    <Card>
      <h2 className="text-h4 font-semibold text-ink">Send with Gmail</h2>
      <p className="mt-1 text-small text-gray-600">
        Sends from {gmail.data?.email}. Nothing is sent until you click Send.
      </p>
      <div className="mt-4 space-y-4">
        <Input
          label="To"
          value={to}
          onChange={(event) => {
            setTo(event.target.value);
          }}
        />
        <Input
          label="Subject"
          value={subject}
          onChange={(event) => {
            setSubject(event.target.value);
          }}
        />
        <Textarea
          label="Message"
          value={body}
          onChange={(event) => {
            setBody(event.target.value);
          }}
        />
        {completedAudit?.has_desktop_screenshot ? (
          <Checkbox
            checked={attachAudit}
            onChange={(event) => {
              setAttachAudit(event.target.checked);
            }}
            label="Attach latest audit screenshot"
          />
        ) : null}
        {readyMockups.length > 0 ? (
          <div className="space-y-2">
            <p className="text-caption font-semibold text-gray-500">Attach mockups</p>
            {readyMockups.map((item) => {
              const checked = mockupIds.includes(item.id);
              return (
                <Checkbox
                  key={item.id}
                  checked={checked}
                  onChange={(event) => {
                    setMockupIds((current) =>
                      event.target.checked
                        ? [...current, item.id]
                        : current.filter((id) => id !== item.id),
                    );
                  }}
                  label={item.title || `Mockup v${item.version}`}
                />
              );
            })}
          </div>
        ) : null}
        <Button
          disabled={!ready || sending || send.isPending}
          isLoading={sending || send.isPending}
          onClick={submit}
        >
          Send
        </Button>
      </div>
    </Card>
  );
}

import { useState } from "react";

import { useToast } from "../../components/feedback/useToast";
import { Button } from "../../components/ui/Button";
import { Card } from "../../components/ui/Card";
import { Select } from "../../components/ui/Select";
import { useGenerateOutreach } from "../../hooks/useOutreach";
import { useOutreachTemplates } from "../../hooks/useWorkspace";
import { apiErrorMessage } from "../../lib/apiError";
import type { Contact } from "../../types/lead";

type OutreachComposerProps = {
  leadId: string;
  contacts: Contact[];
  onCreated: (messageId: string) => void;
};

export function OutreachComposer({ leadId, contacts, onCreated }: OutreachComposerProps) {
  const { notify } = useToast();
  const templates = useOutreachTemplates();
  const generate = useGenerateOutreach(leadId);
  const primary = contacts.find((contact) => contact.is_primary) ?? contacts[0];
  const [templateId, setTemplateId] = useState("");
  const [contactId, setContactId] = useState(primary?.id ?? "");

  const createDraft = () => {
    generate.mutate(
      {
        template_id: templateId || undefined,
        contact_id: contactId || undefined,
      },
      {
        onSuccess: (message) => {
          notify("Draft created. Send it from your email app, then mark it contacted.", "success");
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
      <h2 className="text-h4 font-semibold text-ink">Write an email</h2>
      <p className="mt-2 text-body text-gray-600">
        Create a draft from a template. You send it from your own inbox, then record it here.
      </p>
      <div className="mt-4 grid gap-4 md:grid-cols-2">
        <Select
          label="Template"
          value={templateId}
          onChange={(event) => {
            setTemplateId(event.target.value);
          }}
          placeholder="Homepage concept"
          options={(templates.data ?? [])
            .filter((item) => item.is_active)
            .map((item) => ({ value: item.id, label: item.name }))}
        />
        {contacts.length > 0 ? (
          <Select
            label="Contact"
            value={contactId}
            onChange={(event) => {
              setContactId(event.target.value);
            }}
            options={contacts.map((contact) => ({
              value: contact.id,
              label: [contact.name, contact.email].filter(Boolean).join(" · ") || "Contact",
            }))}
          />
        ) : (
          <p className="self-end text-body text-gray-600">
            Add a contact on Overview if you want the note addressed to someone by name.
          </p>
        )}
      </div>
      <div className="mt-4">
        <Button onClick={createDraft} isLoading={generate.isPending}>
          Create draft
        </Button>
      </div>
    </Card>
  );
}

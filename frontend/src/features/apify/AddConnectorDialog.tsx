import { useState, type FormEvent } from "react";

import { Button } from "../../components/ui/Button";
import { Input } from "../../components/ui/Input";
import { Modal } from "../../components/ui/Modal";
import { useCreateApifyConnector } from "../../hooks/useApify";
import { apiErrorMessage } from "../../lib/apiError";

const ACTOR_REF = /^[A-Za-z0-9][A-Za-z0-9_.~/-]{0,199}$/;

type AddConnectorDialogProps = {
  open: boolean;
  onClose: () => void;
};

export function AddConnectorDialog({ open, onClose }: AddConnectorDialogProps) {
  const create = useCreateApifyConnector();
  const [displayName, setDisplayName] = useState("");
  const [actorId, setActorId] = useState("");
  const [nameError, setNameError] = useState<string | null>(null);
  const [actorError, setActorError] = useState<string | null>(null);
  const [formError, setFormError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  async function onSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (submitting) {
      return;
    }
    const name = displayName.trim();
    const actor = actorId.trim();
    const nextNameError = name ? null : "Enter a display name.";
    const nextActorError = !actor
      ? "Enter an actor ID or owner/name."
      : ACTOR_REF.test(actor) && actor.split("/").length <= 2
        ? null
        : "Enter an actor ID or owner/name.";
    setNameError(nextNameError);
    setActorError(nextActorError);
    setFormError(null);
    if (nextNameError || nextActorError) {
      return;
    }

    setSubmitting(true);
    try {
      await create.mutateAsync({ display_name: name, actor_id: actor });
      setDisplayName("");
      setActorId("");
      onClose();
    } catch (caught) {
      setFormError(apiErrorMessage(caught, "That actor could not be saved."));
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <Modal
      open={open}
      title="Add connector"
      description="Apify checks the actor before it is saved. Only actors your token can access are added."
      onClose={onClose}
    >
      <form className="space-y-4" onSubmit={onSubmit} noValidate>
        <Input
          label="Display name"
          value={displayName}
          error={nameError ?? undefined}
          maxLength={120}
          onChange={(event) => {
            setDisplayName(event.target.value);
          }}
        />
        <Input
          label="Actor ID"
          hint="Use the actor ID, or owner/name such as compass/crawler-google-places."
          value={actorId}
          error={actorError ?? undefined}
          autoCapitalize="off"
          autoCorrect="off"
          spellCheck={false}
          onChange={(event) => {
            setActorId(event.target.value);
          }}
        />
        {formError ? (
          <p className="text-small text-danger" role="alert">
            {formError}
          </p>
        ) : null}
        <div className="flex justify-end gap-2">
          <Button variant="secondary" onClick={onClose} disabled={submitting}>
            Cancel
          </Button>
          <Button type="submit" isLoading={submitting}>
            Add connector
          </Button>
        </div>
      </form>
    </Modal>
  );
}

import { useState } from "react";

import { useToast } from "../../components/feedback/useToast";
import { Button } from "../../components/ui/Button";
import { Input } from "../../components/ui/Input";
import { useCancelFollowup, useCompleteFollowup, useUpdateFollowup } from "../../hooks/useOutreach";
import { apiErrorMessage } from "../../lib/apiError";
import type { FollowupItem } from "../../types/workspace";
import { dateInputToIso, isoToDateInput } from "./dates";

export function FollowUpActions({ item }: { item: FollowupItem }) {
  const { notify } = useToast();
  const complete = useCompleteFollowup();
  const cancel = useCancelFollowup();
  const reschedule = useUpdateFollowup();
  const [confirming, setConfirming] = useState(false);
  const [editing, setEditing] = useState(false);
  const [date, setDate] = useState(isoToDateInput(item.scheduled_for));

  if (item.status === "COMPLETED" || item.status === "CANCELLED") {
    return null;
  }

  return (
    <div className="mt-3 space-y-3">
      <div className="flex flex-wrap gap-2">
        <Button
          variant="secondary"
          isLoading={complete.isPending}
          onClick={() => {
            complete.mutate(item.id, {
              onSuccess: () => {
                notify("Follow-up completed.", "success");
              },
              onError: (error) => {
                notify(apiErrorMessage(error, "Could not complete the follow-up."), "danger");
              },
            });
          }}
        >
          Complete
        </Button>
        <Button
          variant="secondary"
          onClick={() => {
            setEditing((open) => !open);
            setConfirming(false);
          }}
        >
          Reschedule
        </Button>
        {confirming ? (
          <Button
            variant="secondary"
            isLoading={cancel.isPending}
            onClick={() => {
              cancel.mutate(item.id, {
                onSuccess: () => {
                  notify("Follow-up cancelled.", "success");
                  setConfirming(false);
                },
                onError: (error) => {
                  notify(apiErrorMessage(error, "Could not cancel the follow-up."), "danger");
                },
              });
            }}
          >
            Confirm cancel
          </Button>
        ) : (
          <Button
            variant="ghost"
            onClick={() => {
              setConfirming(true);
              setEditing(false);
            }}
          >
            Cancel
          </Button>
        )}
      </div>
      {editing ? (
        <form
          className="flex flex-col gap-3 sm:flex-row sm:items-end"
          onSubmit={(event) => {
            event.preventDefault();
            if (!date) {
              return;
            }
            reschedule.mutate(
              { followupId: item.id, payload: { scheduled_for: dateInputToIso(date) } },
              {
                onSuccess: () => {
                  notify("Follow-up rescheduled.", "success");
                  setEditing(false);
                },
                onError: (error) => {
                  notify(apiErrorMessage(error, "Could not reschedule the follow-up."), "danger");
                },
              },
            );
          }}
        >
          <div className="sm:w-56">
            <Input
              label="New date"
              type="date"
              value={date}
              required
              onChange={(event) => {
                setDate(event.target.value);
              }}
            />
          </div>
          <Button type="submit" isLoading={reschedule.isPending}>
            Save date
          </Button>
        </form>
      ) : null}
    </div>
  );
}

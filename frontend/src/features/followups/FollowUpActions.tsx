import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { ArrowRight, Calendar, Clock } from "lucide-react";

import { useToast } from "../../components/feedback/useToast";
import { Button } from "../../components/ui/Button";
import { Input } from "../../components/ui/Input";
import { useCancelFollowup, useCompleteFollowup, useUpdateFollowup } from "../../hooks/useOutreach";
import { apiErrorMessage } from "../../lib/apiError";
import type { FollowupItem } from "../../types/workspace";
import { dateInputToIso, isoToDateInput } from "./dates";

export function FollowUpActions({ item }: { item: FollowupItem }) {
  const navigate = useNavigate();
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

  const snoozeDays = (days: number, label: string) => {
    const target = new Date(Date.now() + days * 24 * 60 * 60 * 1000);
    target.setHours(9, 0, 0, 0);
    reschedule.mutate(
      { followupId: item.id, payload: { scheduled_for: target.toISOString() } },
      {
        onSuccess: () => {
          notify(`Follow-up snoozed to ${label}.`, "success");
        },
        onError: (error) => {
          notify(apiErrorMessage(error, "Could not snooze the follow-up."), "danger");
        },
      },
    );
  };

  return (
    <div className="mt-3 space-y-3">
      <div className="flex flex-wrap items-center gap-2">
        <Button
          variant="primary"
          className="h-8 px-3 text-small"
          onClick={() => navigate(`/leads/${item.lead_id}?tab=outreach`)}
        >
          <span>Send Follow-up</span>
          <ArrowRight className="size-3.5 ml-1" />
        </Button>

        <Button
          variant="secondary"
          className="h-8 px-2.5 text-small"
          isLoading={complete.isPending}
          onClick={() => {
            complete.mutate(item.id, {
              onSuccess: () => {
                notify("Follow-up marked completed.", "success");
              },
              onError: (error) => {
                notify(apiErrorMessage(error, "Could not complete the follow-up."), "danger");
              },
            });
          }}
        >
          Complete
        </Button>

        {/* Snooze Options */}
        <Button
          variant="secondary"
          className="h-8 px-2 text-caption text-gray-700"
          disabled={reschedule.isPending}
          onClick={() => snoozeDays(1, "tomorrow")}
          title="Snooze 1 day"
        >
          <Clock className="size-3 mr-1 text-gray-400" />
          Tomorrow
        </Button>

        <Button
          variant="secondary"
          className="h-8 px-2 text-caption text-gray-700"
          disabled={reschedule.isPending}
          onClick={() => snoozeDays(7, "next week")}
          title="Snooze 7 days"
        >
          <Calendar className="size-3 mr-1 text-gray-400" />
          Next Week
        </Button>

        <Button
          variant="secondary"
          className="h-8 px-2 text-caption text-gray-700"
          onClick={() => {
            setEditing((open) => !open);
            setConfirming(false);
          }}
        >
          Custom Date
        </Button>

        {confirming ? (
          <Button
            variant="secondary"
            className="h-8 px-2 text-caption text-danger"
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
            className="h-8 px-2 text-caption text-gray-500 hover:text-danger"
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
          className="flex flex-col gap-3 sm:flex-row sm:items-end rounded-lg border border-gray-100 bg-gray-50 p-3"
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
          <div className="flex-1">
            <Input
              label="Reschedule date"
              type="date"
              value={date}
              onChange={(event) => {
                setDate(event.target.value);
              }}
            />
          </div>
          <div className="flex gap-2">
            <Button type="submit" className="h-9 px-3 text-small" isLoading={reschedule.isPending}>
              Save
            </Button>
            <Button
              variant="secondary"
              className="h-9 px-3 text-small"
              onClick={() => {
                setEditing(false);
                setDate(isoToDateInput(item.scheduled_for));
              }}
            >
              Cancel
            </Button>
          </div>
        </form>
      ) : null}
    </div>
  );
}

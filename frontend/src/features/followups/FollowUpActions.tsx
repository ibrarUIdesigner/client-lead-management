import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { ArrowRight, Calendar, Clock, Copy, Sparkles } from "lucide-react";

import { useToast } from "../../components/feedback/useToast";
import { Button } from "../../components/ui/Button";
import { Input } from "../../components/ui/Input";
import { useCancelFollowup, useCompleteFollowup, useUpdateFollowup } from "../../hooks/useOutreach";
import { apiErrorMessage } from "../../lib/apiError";
import { getFollowupDraft, type FollowupDraft } from "../../services/followups";
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
  const [draftOpen, setDraftOpen] = useState(false);
  const [draftData, setDraftData] = useState<FollowupDraft | null>(null);
  const [draftLoading, setDraftLoading] = useState(false);

  if (item.status === "COMPLETED" || item.status === "CANCELLED") {
    return null;
  }

  const handleToggleDraft = async () => {
    if (draftOpen) {
      setDraftOpen(false);
      return;
    }
    if (draftData) {
      setDraftOpen(true);
      return;
    }
    setDraftLoading(true);
    try {
      const data = await getFollowupDraft(item.id);
      setDraftData(data);
      setDraftOpen(true);
    } catch (err) {
      notify(apiErrorMessage(err, "Could not load AI follow-up draft."), "danger");
    } finally {
      setDraftLoading(false);
    }
  };

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
          className="h-8 px-2.5 text-small text-indigo-700 bg-indigo-50 hover:bg-indigo-100 border-indigo-200"
          onClick={() => handleToggleDraft()}
          isLoading={draftLoading}
        >
          <Sparkles className="size-3.5 mr-1 text-indigo-600" />
          <span>{draftOpen ? "Hide AI Draft" : "View AI Draft"}</span>
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

      {draftOpen && draftData ? (
        <div className="rounded-lg border border-indigo-200 bg-gradient-to-br from-indigo-50/70 via-white to-purple-50/30 p-3.5 shadow-2xs space-y-2">
          <div className="flex items-center justify-between gap-2">
            <div className="flex items-center gap-1.5">
              <Sparkles className="size-4 text-indigo-600" />
              <span className="text-small font-bold text-indigo-950">
                Sequence Step {draftData.step}: {draftData.stage_name}
              </span>
            </div>
            <Button
              variant="ghost"
              className="h-6 px-2 text-caption text-gray-500 hover:text-gray-800"
              onClick={() => setDraftOpen(false)}
            >
              Close
            </Button>
          </div>
          <p className="text-caption text-indigo-800">
            <strong>Strategy: </strong>
            {draftData.strategy_notes}
          </p>
          <div className="rounded border border-indigo-100 bg-white p-2.5 text-small text-gray-800">
            <p className="font-semibold text-gray-900 mb-1">Subject: {draftData.subject}</p>
            <p className="whitespace-pre-wrap text-gray-700">{draftData.body}</p>
          </div>
          <div className="flex items-center gap-2 pt-1">
            <Button
              variant="secondary"
              className="h-7 px-2.5 text-caption font-semibold"
              onClick={() => {
                navigator.clipboard.writeText(`Subject: ${draftData.subject}\n\n${draftData.body}`);
                notify("AI follow-up draft copied to clipboard.", "success");
              }}
            >
              <Copy className="size-3 mr-1" />
              Copy Draft
            </Button>
            <Button
              variant="primary"
              className="h-7 px-2.5 text-caption font-semibold"
              onClick={() => navigate(`/leads/${item.lead_id}?tab=outreach`)}
            >
              Use in Outreach
              <ArrowRight className="size-3 ml-1" />
            </Button>
          </div>
        </div>
      ) : null}

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

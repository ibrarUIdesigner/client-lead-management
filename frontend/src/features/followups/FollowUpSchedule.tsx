import { useState } from "react";

import { useToast } from "../../components/feedback/useToast";
import { Button } from "../../components/ui/Button";
import { Input } from "../../components/ui/Input";
import { useScheduleFollowup } from "../../hooks/useOutreach";
import { apiErrorMessage } from "../../lib/apiError";
import { dateInputToIso, defaultFollowUpDate } from "./dates";

type FollowUpScheduleProps = {
  leadId: string;
  outreachId?: string;
};

export function FollowUpSchedule({ leadId, outreachId }: FollowUpScheduleProps) {
  const { notify } = useToast();
  const schedule = useScheduleFollowup();
  const [date, setDate] = useState(defaultFollowUpDate);

  return (
    <form
      className="mt-4 flex flex-col gap-3 border-t border-gray-200 pt-4 sm:flex-row sm:items-end"
      onSubmit={(event) => {
        event.preventDefault();
        if (!date) {
          return;
        }
        schedule.mutate(
          {
            lead_id: leadId,
            outreach_id: outreachId,
            scheduled_for: dateInputToIso(date),
            type: "email",
          },
          {
            onSuccess: () => {
              notify("Follow-up scheduled.", "success");
            },
            onError: (error) => {
              notify(apiErrorMessage(error, "Could not schedule the follow-up."), "danger");
            },
          },
        );
      }}
    >
      <div className="sm:w-56">
        <Input
          label="Follow up on"
          type="date"
          value={date}
          required
          onChange={(event) => {
            setDate(event.target.value);
          }}
        />
      </div>
      <Button type="submit" variant="secondary" isLoading={schedule.isPending}>
        Schedule follow-up
      </Button>
    </form>
  );
}

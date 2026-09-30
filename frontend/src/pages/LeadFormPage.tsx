import { zodResolver } from "@hookform/resolvers/zod";
import { useForm } from "react-hook-form";
import { useNavigate, useParams } from "react-router-dom";

import { useToast } from "../components/feedback/useToast";
import { PageHeader } from "../components/layout/PageHeader";
import { Button } from "../components/ui/Button";
import { Card } from "../components/ui/Card";
import { Skeleton } from "../components/ui/Skeleton";
import { LeadFormFields } from "../features/leads/LeadFormFields";
import {
  emptyLeadForm,
  leadFormSchema,
  leadToForm,
  toLeadPayload,
  type LeadFormValues,
} from "../features/leads/leadForm";
import { useCreateLead, useLead, useUpdateLead } from "../hooks/useLeads";
import { apiErrorCode, apiErrorMessage } from "../lib/apiError";
import { EmptyState } from "../components/feedback/EmptyState";

export function LeadFormPage() {
  const { leadId } = useParams();
  const lead = useLead(leadId);
  const navigate = useNavigate();

  if (leadId && lead.isPending) {
    return (
      <div className="space-y-3" aria-busy="true">
        <Skeleton className="h-10 w-48" />
        <Skeleton className="h-64 w-full" />
      </div>
    );
  }

  if (leadId && lead.isError && apiErrorCode(lead.error) === "LEAD_NOT_FOUND") {
    return (
      <EmptyState
        title="This lead does not exist"
        description="It may have been deleted."
        action={
          <Button
            onClick={() => {
              navigate("/leads");
            }}
          >
            Back to leads
          </Button>
        }
      />
    );
  }

  if (leadId && (lead.isError || !lead.data)) {
    return (
      <EmptyState
        title="This lead could not be loaded"
        description={apiErrorMessage(lead.error, "The lead could not be loaded.")}
        action={
          <Button
            variant="secondary"
            onClick={() => {
              void lead.refetch();
            }}
          >
            Retry
          </Button>
        }
      />
    );
  }

  return (
    <LeadForm
      key={lead.data?.id ?? "new"}
      leadId={leadId}
      initial={lead.data ? leadToForm(lead.data) : emptyLeadForm}
    />
  );
}

type LeadFormProps = {
  leadId?: string;
  initial: LeadFormValues;
};

function LeadForm({ leadId, initial }: LeadFormProps) {
  const navigate = useNavigate();
  const { notify } = useToast();
  const createLead = useCreateLead();
  const updateLead = useUpdateLead(leadId ?? "");
  const {
    register,
    handleSubmit,
    formState: { errors },
  } = useForm<LeadFormValues>({
    resolver: zodResolver(leadFormSchema),
    defaultValues: initial,
  });
  const isSaving = createLead.isPending || updateLead.isPending;

  const onSubmit = (values: LeadFormValues) => {
    const payload = toLeadPayload(values);
    if (leadId) {
      updateLead.mutate(payload, {
        onSuccess: () => {
          notify("Lead saved.", "success");
          navigate(`/leads/${leadId}`);
        },
        onError: (error) => {
          notify(apiErrorMessage(error, "Could not save the lead."), "danger");
        },
      });
      return;
    }

    createLead.mutate(payload, {
      onSuccess: (lead) => {
        notify("Lead added.", "success");
        navigate(`/leads/${lead.id}`);
      },
      onError: (error) => {
        notify(apiErrorMessage(error, "Could not add the lead."), "danger");
      },
    });
  };

  return (
    <>
      <PageHeader
        title={leadId ? "Edit lead" : "Add lead"}
        description="Keep the business, contact, and status details in one place."
      />
      <Card>
        <form className="space-y-6" onSubmit={handleSubmit(onSubmit)} noValidate>
          <LeadFormFields register={register} errors={errors} />
          <div className="flex flex-wrap gap-2">
            <Button type="submit" isLoading={isSaving}>
              {leadId ? "Save lead" : "Add lead"}
            </Button>
            <Button
              variant="secondary"
              onClick={() => {
                navigate(leadId ? `/leads/${leadId}` : "/leads");
              }}
            >
              Cancel
            </Button>
          </div>
        </form>
      </Card>
    </>
  );
}

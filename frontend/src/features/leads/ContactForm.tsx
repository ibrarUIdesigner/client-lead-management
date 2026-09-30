import { zodResolver } from "@hookform/resolvers/zod";
import { useForm } from "react-hook-form";

import { useToast } from "../../components/feedback/useToast";
import { Button } from "../../components/ui/Button";
import { Checkbox } from "../../components/ui/Checkbox";
import { Input } from "../../components/ui/Input";
import { useCreateContact } from "../../hooks/useContacts";
import { apiErrorMessage } from "../../lib/apiError";
import {
  contactFormSchema,
  emptyContactForm,
  toContactPayload,
  type ContactFormValues,
} from "./contactSchema";

type ContactFormProps = {
  leadId: string;
};

export function ContactForm({ leadId }: ContactFormProps) {
  const { notify } = useToast();
  const createContact = useCreateContact(leadId);
  const {
    register,
    handleSubmit,
    reset,
    formState: { errors },
  } = useForm<ContactFormValues>({
    resolver: zodResolver(contactFormSchema),
    defaultValues: emptyContactForm,
  });

  const onSubmit = (values: ContactFormValues) => {
    createContact.mutate(toContactPayload(values), {
      onSuccess: () => {
        notify("Contact added.", "success");
        reset(emptyContactForm);
      },
      onError: (error) => {
        notify(apiErrorMessage(error, "Could not add the contact."), "danger");
      },
    });
  };

  return (
    <form className="grid gap-4 md:grid-cols-2" onSubmit={handleSubmit(onSubmit)} noValidate>
      <Input label="Name" error={errors.name?.message} {...register("name")} />
      <Input label="Job title" error={errors.job_title?.message} {...register("job_title")} />
      <Input label="Email" type="email" error={errors.email?.message} {...register("email")} />
      <Input label="Phone" type="tel" error={errors.phone?.message} {...register("phone")} />
      <div className="md:col-span-2">
        <Input
          label="LinkedIn"
          placeholder="https://"
          error={errors.linkedin_url?.message}
          {...register("linkedin_url")}
        />
      </div>
      <Checkbox label="Primary contact" {...register("is_primary")} />
      <div className="md:col-span-2">
        <Button type="submit" isLoading={createContact.isPending}>
          Add contact
        </Button>
      </div>
    </form>
  );
}

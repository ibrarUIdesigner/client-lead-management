import type { FieldErrors, UseFormRegister } from "react-hook-form";

import { Input } from "../../components/ui/Input";
import { Select } from "../../components/ui/Select";
import { Textarea } from "../../components/ui/Textarea";
import type { LeadFormValues } from "./leadForm";
import { leadStatusOptions } from "./statuses";

type LeadFormFieldsProps = {
  register: UseFormRegister<LeadFormValues>;
  errors: FieldErrors<LeadFormValues>;
};

export function LeadFormFields({ register, errors }: LeadFormFieldsProps) {
  return (
    <div className="grid gap-4 md:grid-cols-2">
      <div className="md:col-span-2">
        <Input
          label="Business name"
          autoComplete="organization"
          error={errors.business_name?.message}
          {...register("business_name")}
        />
      </div>
      <Input label="Industry" error={errors.industry?.message} {...register("industry")} />
      <Input label="Source" error={errors.source?.message} {...register("source")} />
      <Input label="City" error={errors.city?.message} {...register("city")} />
      <Input label="Country" error={errors.country?.message} {...register("country")} />
      <Input
        label="Website"
        type="url"
        placeholder="https://"
        error={errors.website_url?.message}
        {...register("website_url")}
      />
      <Input
        label="Email"
        type="email"
        autoComplete="email"
        error={errors.email?.message}
        {...register("email")}
      />
      <Input label="Phone" type="tel" error={errors.phone?.message} {...register("phone")} />
      <Select
        label="Status"
        options={leadStatusOptions}
        error={errors.lead_status?.message}
        {...register("lead_status")}
      />
      <div className="md:col-span-2">
        <Input
          label="Tags"
          hint="Separate tags with commas."
          error={errors.tags?.message}
          {...register("tags")}
        />
      </div>
      <div className="md:col-span-2">
        <Textarea label="Notes" error={errors.notes?.message} {...register("notes")} />
      </div>
    </div>
  );
}

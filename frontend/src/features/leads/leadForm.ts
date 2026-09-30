import { z } from "zod";

import type { Lead, LeadWrite } from "../../types/lead";
import { LEAD_STATUS_VALUES, type LeadStatus } from "./statuses";

const optionalUrl = z
  .string()
  .trim()
  .refine((value) => value === "" || /^https?:\/\//i.test(value), {
    message: "Start the address with http:// or https://.",
  });

const optionalEmail = z
  .string()
  .trim()
  .refine((value) => value === "" || /^[^@\s]+@[^@\s]+\.[^@\s]+$/.test(value), {
    message: "Enter a valid email.",
  });

export const leadFormSchema = z.object({
  business_name: z.string().trim().min(1, "Enter the business name.").max(255),
  industry: z.string().trim().max(120),
  city: z.string().trim().max(120),
  country: z.string().trim().max(120),
  website_url: optionalUrl,
  email: optionalEmail,
  phone: z.string().trim().max(40),
  source: z.string().trim().max(120),
  tags: z.string().trim(),
  notes: z.string().trim(),
  lead_status: z.enum(LEAD_STATUS_VALUES),
});

export type LeadFormValues = z.infer<typeof leadFormSchema>;

export const emptyLeadForm: LeadFormValues = {
  business_name: "",
  industry: "",
  city: "",
  country: "",
  website_url: "",
  email: "",
  phone: "",
  source: "",
  tags: "",
  notes: "",
  lead_status: "NEW",
};

function emptyToNull(value: string): string | null {
  const trimmed = value.trim();
  return trimmed ? trimmed : null;
}

function isLeadStatus(value: string): value is LeadStatus {
  return LEAD_STATUS_VALUES.some((status) => status === value);
}

export function leadToForm(lead: Lead): LeadFormValues {
  return {
    business_name: lead.business_name,
    industry: lead.industry ?? "",
    city: lead.city ?? "",
    country: lead.country ?? "",
    website_url: lead.website_url ?? "",
    email: lead.email ?? "",
    phone: lead.phone ?? "",
    source: lead.source ?? "",
    tags: lead.tags.join(", "),
    notes: lead.notes ?? "",
    lead_status: isLeadStatus(lead.lead_status) ? lead.lead_status : "NEW",
  };
}

export function toLeadPayload(values: LeadFormValues): LeadWrite {
  return {
    business_name: values.business_name.trim(),
    industry: emptyToNull(values.industry),
    city: emptyToNull(values.city),
    country: emptyToNull(values.country),
    website_url: emptyToNull(values.website_url),
    email: emptyToNull(values.email),
    phone: emptyToNull(values.phone),
    source: emptyToNull(values.source),
    notes: emptyToNull(values.notes),
    tags: values.tags
      .split(",")
      .map((tag) => tag.trim())
      .filter((tag) => tag.length > 0),
    lead_status: values.lead_status,
  };
}

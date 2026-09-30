import { z } from "zod";

import type { ContactWrite } from "../../types/lead";

export const contactFormSchema = z.object({
  name: z.string().trim().min(1, "Enter the contact name.").max(255),
  job_title: z.string().trim().max(120),
  email: z
    .string()
    .trim()
    .refine((value) => value === "" || /^[^@\s]+@[^@\s]+\.[^@\s]+$/.test(value), {
      message: "Enter a valid email.",
    }),
  phone: z.string().trim().max(40),
  linkedin_url: z
    .string()
    .trim()
    .refine((value) => value === "" || /^https?:\/\//i.test(value), {
      message: "Start the address with http:// or https://.",
    }),
  is_primary: z.boolean(),
});

export type ContactFormValues = z.infer<typeof contactFormSchema>;

export const emptyContactForm: ContactFormValues = {
  name: "",
  job_title: "",
  email: "",
  phone: "",
  linkedin_url: "",
  is_primary: false,
};

function emptyToNull(value: string): string | null {
  const trimmed = value.trim();
  return trimmed ? trimmed : null;
}

export function toContactPayload(values: ContactFormValues): ContactWrite {
  return {
    name: values.name.trim(),
    job_title: emptyToNull(values.job_title),
    email: emptyToNull(values.email),
    phone: emptyToNull(values.phone),
    linkedin_url: emptyToNull(values.linkedin_url),
    is_primary: values.is_primary,
  };
}

import { api } from "./api";
import { env } from "../lib/env";
import type {
  MockupCreateWrite,
  MockupCreated,
  MockupDetail,
  MockupEligibility,
  MockupRefineWrite,
  MockupRetryWrite,
} from "../types/mockup";

export async function getMockupEligibility(leadId: string): Promise<MockupEligibility> {
  const { data } = await api.get<MockupEligibility>(`/leads/${leadId}/mockup-eligibility`);
  return data;
}

export async function createMockup(body: MockupCreateWrite, files: File[] = []): Promise<MockupCreated> {
  const timeout = 180_000;
  if (files.length > 0) {
    const form = new FormData();
    form.append("lead_id", body.lead_id);
    form.append("provider", body.provider);
    form.append("goal", body.goal);
    form.append("guide_mode", body.guide_mode);
    if (body.requirements) {
      form.append("requirements", body.requirements);
    }
    if (body.source_mockup_id) {
      form.append("source_mockup_id", body.source_mockup_id);
    }
    if (body.design_guide_id) {
      form.append("design_guide_id", body.design_guide_id);
    }
    for (const file of files) {
      form.append("assets", file);
    }
    const { data } = await api.post<MockupCreated>("/mockups", form, { timeout });
    return data;
  }
  const { data } = await api.post<MockupCreated>("/mockups", body, { timeout });
  return data;
}

export async function getMockup(mockupId: string): Promise<MockupDetail> {
  const { data } = await api.get<MockupDetail>(`/mockups/${mockupId}`);
  return data;
}

export async function processMockup(mockupId: string): Promise<MockupDetail> {
  const { data } = await api.post<MockupDetail>(`/mockups/${mockupId}/process`, null, {
    timeout: 180_000,
  });
  return data;
}

export async function refineMockup(
  mockupId: string,
  body: MockupRefineWrite,
): Promise<MockupCreated> {
  const { data } = await api.post<MockupCreated>(`/mockups/${mockupId}/refine`, body, {
    timeout: 180_000,
  });
  return data;
}

export async function retryMockup(mockupId: string, body: MockupRetryWrite): Promise<MockupCreated> {
  const { data } = await api.post<MockupCreated>(`/mockups/${mockupId}/retry`, body, {
    timeout: 180_000,
  });
  return data;
}

export async function retryMockupScreenshots(mockupId: string): Promise<MockupDetail> {
  const { data } = await api.post<MockupDetail>(`/mockups/${mockupId}/screenshots/retry`);
  return data;
}

export function mockupScreenshotUrl(
  mockupId: string,
  variant: "desktop" | "mobile" | "thumb" = "desktop",
): string {
  return `${env.apiBaseUrl}/mockups/${mockupId}/screenshots/${variant}`;
}

export function mockupHtmlDownloadUrl(mockupId: string): string {
  return `${env.apiBaseUrl}/mockups/${mockupId}/html`;
}

export async function downloadMockupHtml(mockupId: string, filename?: string): Promise<void> {
  const response = await api.get<Blob>(`/mockups/${mockupId}/html`, { responseType: "blob" });
  const url = URL.createObjectURL(response.data);
  const link = document.createElement("a");
  link.href = url;
  link.download = filename || `mockup-${mockupId}.html`;
  link.click();
  URL.revokeObjectURL(url);
}

export async function downloadMockupScreenshot(
  mockupId: string,
  variant: "desktop" | "mobile",
): Promise<void> {
  const response = await api.get<Blob>(`/mockups/${mockupId}/screenshots/${variant}`, {
    responseType: "blob",
  });
  const url = URL.createObjectURL(response.data);
  const link = document.createElement("a");
  link.href = url;
  link.download = `mockup-${mockupId}-${variant}.png`;
  link.click();
  URL.revokeObjectURL(url);
}

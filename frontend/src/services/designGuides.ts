import { api } from "./api";
import type {
  DesignGuide,
  DesignGuideList,
  DesignGuideWrite,
  MockupCreateWrite,
} from "../types/designGuide";

export async function listDesignGuides(query: string, tag: string): Promise<DesignGuideList> {
  const { data } = await api.get<DesignGuideList>("/design-guides", {
    params: {
      q: query || undefined,
      tag: tag || undefined,
    },
  });
  return data;
}

export async function getDesignGuide(guideId: string): Promise<DesignGuide> {
  const { data } = await api.get<DesignGuide>(`/design-guides/${guideId}`);
  return data;
}

export async function getDesignGuideTemplate(): Promise<string> {
  const { data } = await api.get<{ content: string }>("/design-guides/template");
  return data.content;
}

export async function createDesignGuide(body: DesignGuideWrite): Promise<DesignGuide> {
  const { data } = await api.post<DesignGuide>("/design-guides", body);
  return data;
}

export async function updateDesignGuide(
  guideId: string,
  body: DesignGuideWrite,
): Promise<DesignGuide> {
  const { data } = await api.put<DesignGuide>(`/design-guides/${guideId}`, body);
  return data;
}

export async function deleteDesignGuide(guideId: string): Promise<void> {
  await api.delete(`/design-guides/${guideId}`);
}

export async function uploadDesignGuide(form: FormData): Promise<DesignGuide> {
  const { data } = await api.post<DesignGuide>("/design-guides/upload", form);
  return data;
}

export async function downloadDesignGuide(guideId: string, name: string): Promise<void> {
  const response = await api.get<Blob>(`/design-guides/${guideId}/download`, {
    responseType: "blob",
  });
  const url = URL.createObjectURL(response.data);
  const link = document.createElement("a");
  link.href = url;
  link.download = `${name.replace(/[^\w.-]+/g, "-") || "design-guide"}.md`;
  link.click();
  URL.revokeObjectURL(url);
}

export async function createMockupBrief(body: MockupCreateWrite): Promise<{ id: string }> {
  const { data } = await api.post<{ id: string }>("/mockups", body);
  return data;
}

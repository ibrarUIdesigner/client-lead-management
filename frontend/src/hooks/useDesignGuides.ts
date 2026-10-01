import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import {
  createDesignGuide,
  deleteDesignGuide,
  getDesignGuide,
  getDesignGuideTemplate,
  listDesignGuides,
  updateDesignGuide,
  uploadDesignGuide,
} from "../services/designGuides";
import type { DesignGuideWrite } from "../types/designGuide";

export function useDesignGuides(query: string, tag: string) {
  return useQuery({
    queryKey: ["design-guides", query, tag],
    queryFn: () => listDesignGuides(query, tag),
  });
}

export function useDesignGuide(guideId: string | undefined) {
  return useQuery({
    queryKey: ["design-guide", guideId],
    queryFn: () => getDesignGuide(guideId ?? ""),
    enabled: Boolean(guideId),
  });
}

export function useDesignGuideTemplate(enabled: boolean) {
  return useQuery({
    queryKey: ["design-guide-template"],
    queryFn: getDesignGuideTemplate,
    enabled,
  });
}

export function useSaveDesignGuide(guideId?: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (body: DesignGuideWrite) =>
      guideId ? updateDesignGuide(guideId, body) : createDesignGuide(body),
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: ["design-guides"] });
      if (guideId) {
        await queryClient.invalidateQueries({ queryKey: ["design-guide", guideId] });
      }
    },
  });
}

export function useUploadDesignGuide() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: uploadDesignGuide,
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: ["design-guides"] });
    },
  });
}

export function useDeleteDesignGuide() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: deleteDesignGuide,
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: ["design-guides"] });
    },
  });
}

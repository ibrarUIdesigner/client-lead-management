import { useQuery } from "@tanstack/react-query";

import {
  getAnalytics,
  listFollowups,
  listMockups,
  listOutreachMessages,
  listOutreachTemplates,
} from "../services/workspace";

export function useMockups(leadId?: string) {
  return useQuery({
    queryKey: ["mockups", leadId ?? "all"],
    queryFn: () => listMockups(leadId),
    refetchInterval: (query) => {
      const items = query.state.data ?? [];
      if (
        items.some(
          (item) =>
            item.status === "GENERATING" ||
            item.status === "PENDING" ||
            item.screenshot_status === "PENDING",
        )
      ) {
        return 2500;
      }
      return false;
    },
  });
}

export function useOutreachMessages(leadId?: string) {
  return useQuery({
    queryKey: ["outreach", leadId ?? "all"],
    queryFn: () => listOutreachMessages(leadId),
  });
}

export function useOutreachTemplates() {
  return useQuery({
    queryKey: ["outreach-templates"],
    queryFn: listOutreachTemplates,
  });
}

export function useFollowups() {
  return useQuery({
    queryKey: ["followups"],
    queryFn: listFollowups,
  });
}

export function useAnalytics() {
  return useQuery({
    queryKey: ["analytics"],
    queryFn: getAnalytics,
  });
}

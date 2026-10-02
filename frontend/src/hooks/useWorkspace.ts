import { useEffect, useRef } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";

import {
  getAnalytics,
  listFollowups,
  listMockups,
  listOutreachMessages,
  listOutreachTemplates,
} from "../services/workspace";
import { processMockup } from "../services/mockups";

export function useMockups(leadId?: string) {
  const queryClient = useQueryClient();
  const kicked = useRef(new Set<string>());
  const query = useQuery({
    queryKey: ["mockups", leadId ?? "all"],
    queryFn: () => listMockups(leadId),
    refetchInterval: (current) => {
      const items = current.state.data ?? [];
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

  useEffect(() => {
    const items = query.data ?? [];
    for (const item of items) {
      const needsWork =
        item.status === "GENERATING" ||
        item.status === "PENDING" ||
        (item.status === "READY" && item.screenshot_status === "PENDING");
      if (!needsWork || kicked.current.has(item.id)) {
        continue;
      }
      kicked.current.add(item.id);
      void processMockup(item.id)
        .then(() => {
          void queryClient.invalidateQueries({ queryKey: ["mockups"] });
          void queryClient.invalidateQueries({ queryKey: ["mockup", item.id] });
        })
        .catch(() => {
          // Allow another kick later if the first attempt failed immediately.
          kicked.current.delete(item.id);
        });
    }
  }, [query.data, queryClient]);

  return query;
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

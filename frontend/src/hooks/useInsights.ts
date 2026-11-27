import { useMutation, useQuery } from "@tanstack/react-query";

import { getInsights, previewReport, sendReportNow } from "../services/insights";

export function useInsights(days = 90) {
  return useQuery({
    queryKey: ["insights", days],
    queryFn: () => getInsights(days),
    refetchInterval: 60_000,
  });
}

export function useReportActions() {
  return {
    preview: useMutation({ mutationFn: previewReport }),
    send: useMutation({ mutationFn: sendReportNow }),
  };
}

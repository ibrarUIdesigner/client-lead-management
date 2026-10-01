import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import {
  abortApifyRun,
  createApifyConnector,
  deleteApifyConnector,
  getApify,
  getApifyItems,
  importApifyItems,
  startApifyRun,
} from "../services/apify";
import { ACTIVE_RUN_STATUSES, type ApifyRunWrite } from "../types/apify";

export function useApify() {
  return useQuery({
    queryKey: ["apify"],
    queryFn: getApify,
    refetchInterval: (query) =>
      query.state.data?.runs.some((run) => ACTIVE_RUN_STATUSES.has(run.status)) ? 3000 : false,
  });
}

export function useCreateApifyConnector() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: createApifyConnector,
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: ["apify"] });
    },
  });
}

export function useDeleteApifyConnector() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: deleteApifyConnector,
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: ["apify"] });
    },
  });
}

export function useStartApifyRun() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ connectorId, payload }: { connectorId: string; payload: ApifyRunWrite }) =>
      startApifyRun(connectorId, payload),
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: ["apify"] });
    },
  });
}

export function useAbortApifyRun() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: abortApifyRun,
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: ["apify"] });
    },
  });
}

export function useApifyItems(runId: string | null, offset: number, enabled: boolean) {
  return useQuery({
    queryKey: ["apify", "items", runId, offset],
    queryFn: () => getApifyItems(runId ?? "", offset, 25),
    enabled: Boolean(runId) && enabled,
  });
}

export function useImportApifyItems() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ runId, itemKeys }: { runId: string; itemKeys: string[] }) =>
      importApifyItems(runId, itemKeys),
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: ["leads"] });
    },
  });
}

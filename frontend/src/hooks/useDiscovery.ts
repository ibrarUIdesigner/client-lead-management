import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import {
  createDiscoverySearch,
  deleteDiscoverySearch,
  getDiscovery,
  runDiscovery,
  updateDiscoverySearch,
} from "../services/discovery";
import type { DiscoverySearchWrite } from "../types/discovery";

export function useDiscovery() {
  return useQuery({
    queryKey: ["discovery"],
    queryFn: getDiscovery,
    refetchInterval: (query) => (query.state.data?.running ? 2000 : false),
  });
}

export function useCreateDiscoverySearch() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (payload: DiscoverySearchWrite) => createDiscoverySearch(payload),
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: ["discovery"] });
    },
  });
}

export function useUpdateDiscoverySearch() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ id, isActive }: { id: string; isActive: boolean }) =>
      updateDiscoverySearch(id, { is_active: isActive }),
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: ["discovery"] });
    },
  });
}

export function useDeleteDiscoverySearch() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (id: string) => deleteDiscoverySearch(id),
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: ["discovery"] });
    },
  });
}

export function useRunDiscovery() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (searchId?: string) => runDiscovery(searchId),
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: ["discovery"] });
    },
  });
}

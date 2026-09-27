import { keepPreviousData, useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { api } from "./client";
import type { Analysis, Filters, Label, Match, Meta, PlayerGames, SyncJob, Team, TeamInput, TeamReport } from "./types";

export const useMeta = () =>
  useQuery({ queryKey: ["meta"], queryFn: () => api<Meta>("/meta"), staleTime: Infinity });

export const usePlayerGames = (name: string, tag: string, count: number) =>
  useQuery({
    queryKey: ["player", name.toLowerCase(), tag.toLowerCase(), count],
    queryFn: () =>
      api<PlayerGames>(`/players/${encodeURIComponent(name)}/${encodeURIComponent(tag)}/games`, { query: { count } }),
    placeholderData: keepPreviousData,
  });

export const useMatch = (matchId: string) =>
  useQuery({ queryKey: ["match", matchId], queryFn: () => api<Match>(`/matches/${encodeURIComponent(matchId)}`) });

export const useAnalysis = (ids: string[], focus: string[], team?: number) =>
  useQuery({
    queryKey: ["analysis", ids, focus, team],
    queryFn: () => api<Analysis>("/analysis", { query: { m: ids, focus, team } }),
    enabled: ids.length > 0,
  });

export const useTeams = () => useQuery({ queryKey: ["teams"], queryFn: () => api<Team[]>("/teams") });

export const useTeam = (id: number | undefined) =>
  useQuery({ queryKey: ["team", id], queryFn: () => api<Team>(`/teams/${id}`), enabled: id !== undefined });

export const useTeamReport = (id: number, filters: Partial<Filters>) =>
  useQuery({
    queryKey: ["team", id, "report", filters],
    queryFn: () => api<TeamReport>(`/teams/${id}/report`, { query: { ...filters } }),
    placeholderData: keepPreviousData,
  });

export const useSyncStatus = (id: number, enabled: boolean) =>
  useQuery({
    queryKey: ["team", id, "sync"],
    queryFn: () => api<SyncJob | null>(`/teams/${id}/sync`),
    enabled,
    refetchInterval: (query) => (query.state.data?.status === "running" ? 1000 : false),
  });

export function useSaveTeam(id?: number) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (body: TeamInput) =>
      api<Team>(id ? `/teams/${id}` : "/teams", { method: id ? "PUT" : "POST", body: JSON.stringify(body) }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["team"] }).then(() => qc.invalidateQueries({ queryKey: ["teams"] })),
  });
}

export function useDeleteTeam() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (id: number) => api<void>(`/teams/${id}`, { method: "DELETE" }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["teams"] }),
  });
}

export function useStartSync(id: number) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: () => api<SyncJob>(`/teams/${id}/sync`, { method: "POST" }),
    onSuccess: (job) => qc.setQueryData(["team", id, "sync"], job),
  });
}

export function useUpdateTeamGame(teamId: number) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ matchId, ...body }: { matchId: string; label?: Label; included?: boolean }) =>
      api<void>(`/teams/${teamId}/games/${encodeURIComponent(matchId)}`, { method: "PATCH", body: JSON.stringify(body) }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["team", teamId, "report"] }),
  });
}

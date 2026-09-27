import { keepPreviousData, useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { api } from "./client";
import type {
  Analysis, Filters, Group, GroupCompare, GroupEntry, GroupFilters, GroupSummary, Label, LinkCode, Match, Me, Meta, PlayerFilters, PlayerReportData, SavedView, ScoutMode, ScoutPlayer, ScoutReport, ScoutSummary, SyncJob,
  Team, TeamInput, TeamReport,
} from "./types";

export const useMeta = () =>
  useQuery({ queryKey: ["meta"], queryFn: () => api<Meta>("/meta"), staleTime: Infinity });

export const useMatch = (matchId: string) =>
  useQuery({ queryKey: ["match", matchId], queryFn: () => api<Match>(`/matches/${encodeURIComponent(matchId)}`) });

export const useAnalysis = (ids: string[], focus: string[], team?: number) =>
  useQuery({
    queryKey: ["analysis", ids, focus, team],
    queryFn: () => api<Analysis>("/analysis", { query: { m: ids, focus, team } }),
    enabled: ids.length > 0,
    placeholderData: keepPreviousData,
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
    mutationFn: ({ matchId, ...body }: { matchId: string; label?: Label; included?: boolean; opponent?: string }) =>
      api<void>(`/teams/${teamId}/games/${encodeURIComponent(matchId)}`, { method: "PATCH", body: JSON.stringify(body) }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["team", teamId, "report"] }),
  });
}

// ---------------------------------------------------------------- Konten
export const useMe = (poll = false) =>
  useQuery({ queryKey: ["me"], queryFn: () => api<Me>("/auth/me"), refetchInterval: poll ? 3000 : false });

/** Nach An-/Abmeldung ändern sich Sichtbarkeiten überall – alles neu laden. */
function useResetAll() {
  const qc = useQueryClient();
  return () => qc.invalidateQueries();
}

export function useLogin() {
  const reset = useResetAll();
  return useMutation({
    mutationFn: (body: { username: string; password: string }) =>
      api<Me>("/auth/login", { method: "POST", body: JSON.stringify(body) }),
    onSuccess: reset,
  });
}

export function useRegister() {
  const reset = useResetAll();
  return useMutation({
    mutationFn: (body: { username: string; password: string }) =>
      api<Me>("/auth/register", { method: "POST", body: JSON.stringify(body) }),
    onSuccess: reset,
  });
}

export function useLogout() {
  const reset = useResetAll();
  return useMutation({ mutationFn: () => api<void>("/auth/logout", { method: "POST" }), onSuccess: reset });
}

export const useChangePassword = () =>
  useMutation({
    mutationFn: (body: { old_password: string; new_password: string }) =>
      api<void>("/auth/password", { method: "POST", body: JSON.stringify(body) }),
  });

export const useLinkCode = () =>
  useMutation({ mutationFn: () => api<LinkCode>("/me/link-code", { method: "POST" }) });

export function useUnlink() {
  const reset = useResetAll();
  return useMutation({
    mutationFn: (puuid: string) => api<void>(`/me/riot/${encodeURIComponent(puuid)}`, { method: "DELETE" }),
    onSuccess: reset,
  });
}

// -------------------------------------------------------------- Scouting
export const useRecentScouts = () =>
  useQuery({ queryKey: ["scouts"], queryFn: () => api<ScoutSummary[]>("/scout") });

export const useScoutReport = (key: string, filters: Partial<Filters>, focus: string[] = [], match?: ScoutMode) =>
  useQuery({
    queryKey: ["scout", key, "report", filters, focus, match],
    queryFn: () => api<ScoutReport>(`/scout/${encodeURIComponent(key)}`, { query: { ...filters, focus, match } }),
    placeholderData: keepPreviousData,
    retry: false,
  });

export const useScoutStatus = (key: string, enabled: boolean) =>
  useQuery({
    queryKey: ["scout", key, "status"],
    queryFn: () => api<SyncJob | null>(`/scout/${encodeURIComponent(key)}/status`),
    enabled,
    refetchInterval: (query) => (query.state.data?.status === "running" ? 1000 : false),
  });

export function useStartScout() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ riotIds, mode = "all" }: { riotIds: string[]; mode?: ScoutMode }) =>
      api<{ key: string; mode: ScoutMode; players: ScoutPlayer[]; job: SyncJob }>("/scout", {
        method: "POST", body: JSON.stringify({ riot_ids: riotIds, mode }),
      }),
    onSuccess: (res) => qc.setQueryData(["scout", res.key, "status"], res.job),
  });
}

// ------------------------------------------------------------ Ansichten
export const useViews = (enabled: boolean) =>
  useQuery({ queryKey: ["views"], queryFn: () => api<SavedView[]>("/me/views"), enabled });

export function useSaveView() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (view: { id?: number; name?: string; panels?: string[]; is_default?: boolean }) => {
      const { id, ...body } = view;
      return id === undefined
        ? api<SavedView>("/me/views", { method: "POST", body: JSON.stringify(body) })
        : api<SavedView>(`/me/views/${id}`, { method: "PATCH", body: JSON.stringify(body) });
    },
    onSuccess: () => qc.invalidateQueries({ queryKey: ["views"] }),
  });
}

export function useDeleteView() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (id: number) => api<void>(`/me/views/${id}`, { method: "DELETE" }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["views"] }),
  });
}

// ------------------------------------------------------- Spieler-Einzelansicht
const playerPath = (name: string, tag: string) => `/players/${encodeURIComponent(name)}/${encodeURIComponent(tag)}`;

export const usePlayerReport = (name: string, tag: string, filters: Partial<PlayerFilters>) =>
  useQuery({
    queryKey: ["player", name, tag, "report", filters],
    queryFn: () => api<PlayerReportData>(`${playerPath(name, tag)}/report`, { query: { ...filters } }),
    placeholderData: keepPreviousData,
    retry: false,
  });

export const usePlayerSync = (name: string, tag: string, enabled: boolean) =>
  useQuery({
    queryKey: ["player", name, tag, "sync"],
    queryFn: () => api<SyncJob | null>(`${playerPath(name, tag)}/sync`),
    enabled,
    refetchInterval: (query) => (query.state.data?.status === "running" ? 1000 : false),
  });

export function useStartPlayerSync(name: string, tag: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: () => api<SyncJob>(`${playerPath(name, tag)}/sync`, { method: "POST" }),
    onSuccess: (job) => qc.setQueryData(["player", name, tag, "sync"], job),
  });
}

// ---------------------------------------------------------------- Gruppen
export const useGroups = (enabled = true) =>
  useQuery({ queryKey: ["groups"], queryFn: () => api<GroupSummary[]>("/groups"), enabled });

export const useGroupCompare = (key: string, filters: Partial<GroupFilters>) =>
  useQuery({
    queryKey: ["group", key, "compare", filters],
    queryFn: () => api<GroupCompare>(`/groups/${encodeURIComponent(key)}/compare`, { query: { ...filters } }),
    placeholderData: keepPreviousData,
    retry: false,
    // solange ein Team noch synchronisiert/gescoutet wird, regelmäßig nachladen
    refetchInterval: (query) => (query.state.data?.teams.some((t) => t.syncing) ? 3000 : false),
  });

export function useCreateGroup() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (body: { name: string; entries?: GroupEntry[] }) =>
      api<Group>("/groups", { method: "POST", body: JSON.stringify(body) }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["groups"] }),
  });
}

export function useUpdateGroup() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ key, ...body }: { key: string; name?: string; entries?: GroupEntry[] }) =>
      api<Group>(`/groups/${encodeURIComponent(key)}`, { method: "PATCH", body: JSON.stringify(body) }),
    onSuccess: (group) =>
      qc.invalidateQueries({ queryKey: ["group", group.key] }).then(() => qc.invalidateQueries({ queryKey: ["groups"] })),
  });
}

export function useDeleteGroup() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (key: string) => api<void>(`/groups/${encodeURIComponent(key)}`, { method: "DELETE" }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["groups"] }),
  });
}

export function useAddGroupEntry() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ key, entry }: { key: string; entry: GroupEntry }) =>
      api<Group>(`/groups/${encodeURIComponent(key)}/entries`, { method: "POST", body: JSON.stringify(entry) }),
    onSuccess: (group) =>
      qc.invalidateQueries({ queryKey: ["group", group.key] }).then(() => qc.invalidateQueries({ queryKey: ["groups"] })),
  });
}

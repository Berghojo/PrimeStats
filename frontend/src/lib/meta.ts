import { useMeta } from "../api/hooks";

const CDN = "https://ddragon.leagueoflegends.com/cdn";

/** Zugriff auf Championdaten, Positions- und Labelnamen aus /api/meta. */
export function useGameData() {
  const { data } = useMeta();
  return {
    meta: data,
    champion(key: number) {
      const c = data?.champions[String(key)];
      return c ?? { id: "", name: key > 0 ? `#${key}` : "–" };
    },
    iconUrl(key: number) {
      const c = data?.champions[String(key)];
      return c && data ? `${CDN}/${data.ddragon_version}/img/champion/${c.id}.png` : "";
    },
    mapUrl: data ? `${CDN}/${data.ddragon_version}/img/map/map11.png` : "",
    position: (p: string) => data?.positions[p] ?? (p || "–"),
    label: (l: string) => data?.labels[l] ?? l,
  };
}

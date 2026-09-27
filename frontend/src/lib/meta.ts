import { useMeta } from "../api/hooks";

const CDN = "https://ddragon.leagueoflegends.com/cdn";

/** Summoner Spells: ID -> Data-Dragon-Schlüssel */
const SPELLS: Record<number, string> = {
  1: "SummonerBoost", 3: "SummonerExhaust", 4: "SummonerFlash", 6: "SummonerHaste", 7: "SummonerHeal",
  11: "SummonerSmite", 12: "SummonerTeleport", 14: "SummonerDot", 21: "SummonerBarrier", 32: "SummonerSnowball",
};

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
    itemUrl: (id: number) => (data && id ? `${CDN}/${data.ddragon_version}/img/item/${id}.png` : ""),
    spellUrl: (id: number) => (data && SPELLS[id] ? `${CDN}/${data.ddragon_version}/img/spell/${SPELLS[id]}.png` : ""),
    position: (p: string) => data?.positions[p] ?? (p || "–"),
    label: (l: string) => data?.labels[l] ?? l,
  };
}

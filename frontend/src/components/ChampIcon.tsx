import { useState } from "react";

import { useGameData } from "../lib/meta";

interface Props {
  id: number;
  size?: "sm" | "lg";
  ban?: boolean;
}

export function ChampIcon({ id, size, ban }: Props) {
  const { champion, iconUrl } = useGameData();
  const [broken, setBroken] = useState(false);
  const champ = champion(id);
  const url = iconUrl(id);
  return (
    <span className={["champ", size, ban && "ban"].filter(Boolean).join(" ")} title={champ.name}>
      {champ.name.slice(0, 2)}
      {url && !broken && <img src={url} alt={champ.name} loading="lazy" onError={() => setBroken(true)} />}
    </span>
  );
}

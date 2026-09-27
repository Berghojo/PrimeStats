import { useState } from "react";

import { useGameData } from "../lib/meta";

/** Item-Symbol (leerer Platz, wenn kein Item oder das Bild nicht lädt) */
export function ItemIcon({ id }: { id: number }) {
  const { itemUrl } = useGameData();
  const [failed, setFailed] = useState(false);
  const url = itemUrl(id);
  return (
    <span className="item-icon">
      {url && !failed && <img src={url} alt="" loading="lazy" onError={() => setFailed(true)} />}
    </span>
  );
}

export function SpellIcon({ id }: { id: number }) {
  const { spellUrl } = useGameData();
  const [failed, setFailed] = useState(false);
  const url = spellUrl(id);
  return (
    <span className="item-icon spell">
      {url && !failed && <img src={url} alt="" loading="lazy" onError={() => setFailed(true)} />}
    </span>
  );
}

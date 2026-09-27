import { useState } from "react";
import { useParams, useSearchParams } from "react-router-dom";

import { usePlayerGames } from "../api/hooks";
import { GameCard } from "../components/GameCard";
import { SelectionBar, toggle } from "../components/SelectionBar";
import { Empty, ErrorBox, Loading, Spinner } from "../components/ui";

export function PlayerPage() {
  const { name = "", tag = "" } = useParams();
  const [params, setParams] = useSearchParams();
  const count = Number(params.get("count") ?? 20);
  const { data, error, isPending, isFetching } = usePlayerGames(name, tag, count);
  const [selected, setSelected] = useState<Set<string>>(new Set());

  if (isPending) return <Loading message="Lade Custom Games … (beim ersten Abruf kann das dauern)" />;
  if (error) return <ErrorBox error={error} />;

  const { account, games } = data;
  return (
    <>
      <section className="row between">
        <div>
          <h1>{account.game_name}<span className="muted">#{account.tag_line}</span></h1>
          <div className="muted">{games.length} Custom Games / Turnierspiele aus den letzten {count} Einträgen</div>
        </div>
        <label className="field">
          Anzahl Spiele {isFetching && <Spinner />}
          <select value={count} onChange={(e) => setParams({ count: e.target.value })}>
            {[10, 20, 40, 60].map((n) => <option key={n} value={n}>{n}</option>)}
          </select>
        </label>
      </section>
      {games.length === 0 ? (
        <Empty>Keine Custom Games oder Turnierspiele gefunden.</Empty>
      ) : (
        <section>
          <div className="games">
            {games.map((g) => (
              <GameCard
                key={g.match_id}
                match={g}
                focus={account.puuid}
                selected={selected.has(g.match_id)}
                onToggle={() => setSelected((s) => toggle(s, g.match_id))}
              />
            ))}
          </div>
          <SelectionBar
            selected={selected}
            focus={[account.puuid]}
            onSelect={(mode) => setSelected(mode === "none" ? new Set() : new Set(games.map((g) => g.match_id)))}
          />
        </section>
      )}
    </>
  );
}

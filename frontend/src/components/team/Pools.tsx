import type { BanStat, PickStat, PlayerReport } from "../../api/types";
import { num, pct, tone } from "../../lib/format";
import { useGameData } from "../../lib/meta";
import { ChampIcon } from "../ChampIcon";

export function ChampionPools({ players }: { players: PlayerReport[] }) {
  const { champion, position } = useGameData();
  return (
    <section>
      <h2>Champion-Pools</h2>
      <div className="grid three">
        {players.filter((p) => p.member).map((p) => {
          const top = p.champions[0]?.games || 1;
          return (
            <div className="card" key={p.puuid}>
              <div className="row between">
                <h3>{p.name}</h3>
                <span className="muted small">{position(p.position)} · {p.champions.length} Champs</span>
              </div>
              <div className="pool">
                {p.champions.slice(0, 8).map((c) => (
                  <div className="pool-item" key={c.champion_id}>
                    <ChampIcon id={c.champion_id} size="sm" />
                    <div>
                      <div className="row between small"><span>{champion(c.champion_id).name}</span><span className="muted">{num(c.kda)} KDA</span></div>
                      <div className="bar"><span style={{ width: `${(100 * c.games) / top}%` }} /></div>
                    </div>
                    <span className="small nowrap">{c.games}×</span>
                    <span className={`small nowrap ${tone(c.winrate, 0.5)}`}>{pct(c.winrate)}</span>
                  </div>
                ))}
              </div>
            </div>
          );
        })}
      </div>
    </section>
  );
}

function PickList({ title, picks, showPlayers }: { title: string; picks: PickStat[]; showPlayers?: boolean }) {
  const { champion } = useGameData();
  return (
    <div className="list-compact">
      <div className="muted small">{title}</div>
      {picks.slice(0, 10).map((c) => (
        <div className="item" key={c.champion_id}>
          <ChampIcon id={c.champion_id} size="sm" />
          <span className="grow">
            {champion(c.champion_id).name}
            {showPlayers && <span className="muted small"> {c.players.join(", ")}</span>}
          </span>
          <span>{c.games}×</span>
          <span className={tone(c.winrate, 0.5)}>{pct(c.winrate)}</span>
        </div>
      ))}
      {picks.length === 0 && <span className="muted">–</span>}
    </div>
  );
}

function BanList({ title, bans }: { title: string; bans: BanStat[] }) {
  const { champion } = useGameData();
  return (
    <div className="list-compact">
      <div className="muted small">{title}</div>
      {bans.slice(0, 10).map((b) => (
        <div className="item" key={b.champion_id}>
          <ChampIcon id={b.champion_id} size="sm" />
          <span className="grow">{champion(b.champion_id).name}</span>
          <span>{b.count}×</span>
        </div>
      ))}
      {bans.length === 0 && <span className="muted">–</span>}
    </div>
  );
}

export function DraftCards(props: { picks: PickStat[]; ourBans: BanStat[]; enemyBans: BanStat[]; enemyPicks: PickStat[] }) {
  return (
    <section className="grid two">
      <div className="card">
        <h2>Draft – eigene Picks &amp; Bans</h2>
        <div className="split">
          <PickList title="Meistgespielt" picks={props.picks} showPlayers />
          <BanList title="Eigene Bans" bans={props.ourBans} />
        </div>
      </div>
      <div className="card">
        <h2>Draft – Gegner</h2>
        <div className="split">
          <BanList title="Gegen uns gebannt" bans={props.enemyBans} />
          <PickList title="Gegnerische Picks (unsere WR)" picks={props.enemyPicks} />
        </div>
      </div>
    </section>
  );
}

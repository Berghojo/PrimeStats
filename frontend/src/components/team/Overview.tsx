import type { MonsterStat, Overview as OverviewData } from "../../api/types";
import { duration, num, pct, signed, tone } from "../../lib/format";
import { Kpi } from "../ui";

export function OverviewKpis({ ov }: { ov: OverviewData }) {
  return (
    <section className="kpis">
      <Kpi label="Spiele" value={ov.games} hint={`${ov.wins} S · ${ov.losses} N`} />
      <Kpi label="Winrate" value={pct(ov.winrate)} meter={ov.winrate} />
      <Kpi label="Blau" value={pct(ov.blue_winrate)} hint={`${ov.blue_wins}/${ov.blue_games} Siege`} meter={ov.blue_winrate} />
      <Kpi label="Rot" value={pct(ov.red_winrate)} hint={`${ov.red_wins}/${ov.red_games} Siege`} meter={ov.red_winrate} />
      <Kpi label="Ø Spieldauer" value={duration(ov.duration)}
        hint={`Siege ${duration(ov.duration_win)} · Niederl. ${duration(ov.duration_loss)}`} />
      <Kpi label="Ø Kills / Tode" value={`${num(ov.kills)} / ${num(ov.deaths)}`} />
      <Kpi label="Gold @10" value={<span className={tone(ov.gd10)}>{signed(ov.gd10)}</span>} hint="Ø Teamgold-Differenz" />
      <Kpi label="Gold @15" value={<span className={tone(ov.gd15)}>{signed(ov.gd15)}</span>} hint={`aus ${ov.timeline_games} Timelines`} />
      <Kpi label="First Blood" value={pct(ov.first_blood)} meter={ov.first_blood} />
      <Kpi label="Erster Turm" value={pct(ov.first_tower)} meter={ov.first_tower}
        hint={`Ø Türme ${num(ov.towers)} : ${num(ov.towers_lost)}`} />
      <Kpi label="Erster Drache" value={pct(ov.first_dragon)} meter={ov.first_dragon} />
      <Kpi label="Erste Grubs" value={pct(ov.first_grubs)} meter={ov.first_grubs} />
    </section>
  );
}

export function ObjectivesCard({ monsters, ov }: { monsters: MonsterStat[]; ov: OverviewData }) {
  return (
    <div className="card">
      <h2>Objectives</h2>
      <div className="sub">Pro Spiel; Anteil = eigene / alle getöteten Monster.</div>
      <div className="table-wrap">
        <table className="data">
          <thead>
            <tr><th className="left">Objective</th><th>Ø Wir</th><th>Ø Gegner</th><th>Anteil</th><th>Ø Zeit (1. eigener)</th></tr>
          </thead>
          <tbody>
            {monsters.map((m) => (
              <tr key={m.key}>
                <td className="left">{m.label}</td>
                <td>{num(m.us_avg, 2)}</td>
                <td>{num(m.them_avg, 2)}</td>
                <td className={tone(m.share, 0.5)}>{pct(m.share)}</td>
                <td>{m.first_time === null ? "–" : duration(m.first_time * 60)}</td>
              </tr>
            ))}
            <tr><td className="left">Erster Herald</td><td colSpan={4}>{pct(ov.first_herald)}</td></tr>
            <tr><td className="left">Erster Baron</td><td colSpan={4}>{pct(ov.first_baron)}</td></tr>
          </tbody>
        </table>
      </div>
    </div>
  );
}

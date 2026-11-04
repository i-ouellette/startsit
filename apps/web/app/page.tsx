"use client";

import { useEffect, useMemo, useState } from "react";
import { RangeBar } from "@/components/RangeBar";
import { api, type League, type Lineup, type Player, type UserLeagues } from "@/lib/api";

const SCORING_LABEL: Record<string, string> = { ppr: "PPR", half_ppr: "Half PPR", standard: "Standard" };

function riskLabel(r: number) {
  if (r <= -0.6) return "Playing it safe";
  if (r < -0.15) return "Leaning safe";
  if (r <= 0.15) return "Straight medians";
  if (r < 0.6) return "Leaning boom";
  return "Swinging big";
}

export default function Home() {
  const [username, setUsername] = useState("");
  const [user, setUser] = useState<UserLeagues | null>(null);
  const [league, setLeague] = useState<League | null>(null);
  const [risk, setRisk] = useState(0);
  const [lineup, setLineup] = useState<Lineup | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [alertsOn, setAlertsOn] = useState(false);

  async function findLeagues(e: React.FormEvent) {
    e.preventDefault();
    if (!username.trim()) return;
    setLoading(true);
    setError(null);
    setLeague(null);
    setLineup(null);
    try {
      const data = await api.leagues(username.trim());
      setUser(data);
      if (data.leagues.length === 1) setLeague(data.leagues[0]);
    } catch (err) {
      setUser(null);
      setError(err instanceof Error ? err.message : "Couldn't reach Sleeper.");
    } finally {
      setLoading(false);
    }
  }

  // Refetch the lineup when the league or risk changes (debounced for the slider).
  useEffect(() => {
    if (!user || !league) return;
    const ctrl = new AbortController();
    const t = setTimeout(async () => {
      try {
        setError(null);
        setLineup(await api.lineup(league.league_id, user.user_id, risk, ctrl.signal));
      } catch (err) {
        if (!ctrl.signal.aborted) setError(err instanceof Error ? err.message : "Lineup failed to load.");
      }
    }, 180);
    return () => {
      clearTimeout(t);
      ctrl.abort();
    };
  }, [user, league, risk]);

  const scaleMax = useMemo(() => {
    if (!lineup) return 30;
    const all = [...lineup.lineup.map((s) => s.player), ...lineup.bench];
    const top = Math.max(...all.map((p) => p?.projection?.ceiling ?? 0));
    return Math.max(20, Math.ceil(top / 5) * 5);
  }, [lineup]);

  async function turnOnAlerts() {
    if (!user || !league) return;
    try {
      await api.subscribe(league.league_id, user.user_id, risk);
      setAlertsOn(true);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Couldn't turn on alerts.");
    }
  }

  return (
    <main className="page">
      <header className="masthead">
        <h1>Who&rsquo;s starting this week?</h1>
        <p>Enter your Sleeper username. We&rsquo;ll read your roster and build your best lineup for how much risk you want to take.</p>
        <form className="lookup" onSubmit={findLeagues}>
          <label htmlFor="username" className="sr-only">Sleeper username</label>
          <input
            id="username"
            placeholder="Sleeper username"
            value={username}
            onChange={(e) => setUsername(e.target.value)}
            autoComplete="off"
            spellCheck={false}
          />
          <button type="submit" disabled={loading}>{loading ? "Finding…" : "Find my leagues"}</button>
        </form>
      </header>

      {error && <p className="error" role="alert">{error}</p>}

      {user && user.leagues.length === 0 && (
        <p className="empty">No leagues this season for {user.display_name ?? user.username}. Check the username, or join a league on Sleeper first.</p>
      )}

      {user && user.leagues.length > 1 && (
        <nav className="leagues" aria-label="Your leagues">
          {user.leagues.map((lg) => (
            <button
              key={lg.league_id}
              className={lg.league_id === league?.league_id ? "is-active" : ""}
              onClick={() => { setLeague(lg); setAlertsOn(false); }}
            >
              {lg.name}
              <small>{SCORING_LABEL[lg.scoring] ?? lg.scoring} · {lg.total_rosters} teams</small>
            </button>
          ))}
        </nav>
      )}

      {league && lineup && (
        <section className="board">
          <div className="dial">
            <div className="dial__head">
              <span className="dial__value">{riskLabel(risk)}</span>
              <span className="dial__total">{lineup.projected_total.toFixed(1)} pts</span>
            </div>
            <input
              type="range"
              min={-1}
              max={1}
              step={0.05}
              value={risk}
              onChange={(e) => setRisk(Number(e.target.value))}
              aria-label="Risk: play it safe to swing big"
            />
            <div className="dial__ends"><span>Play it safe</span><span>Swing big</span></div>
            <p className="dial__hint">Favored this week? Play it safe. Underdog? Swing big.</p>
          </div>

          {lineup.swaps.length > 0 ? (
            <ul className="swaps">
              {lineup.swaps.map((s) => (
                <li key={s.start.player_id}>
                  Start <strong>{s.start.name}</strong>
                  {s.sit ? <> over <strong>{s.sit.name}</strong></> : <> at {s.slot}</>}
                  <span className="gain">+{s.gain.toFixed(1)}</span>
                </li>
              ))}
            </ul>
          ) : (
            <p className="settled">Your current lineup is already the best one at this risk level.</p>
          )}

          <ol className="lineup" aria-label={`Week ${lineup.week} lineup`}>
            {lineup.lineup.map((s, i) => (
              <Row key={`${s.slot}-${i}`} slot={s.slot} player={s.player} max={scaleMax} />
            ))}
          </ol>

          <details className="bench">
            <summary>Bench ({lineup.bench.length})</summary>
            <ol className="lineup">
              {lineup.bench.map((p) => <Row key={p.player_id} slot="BN" player={p} max={scaleMax} />)}
            </ol>
          </details>

          <div className="alerts">
            {alertsOn ? (
              <p>Alerts are on. If a starter is ruled out before kickoff, you&rsquo;ll get the best swap.</p>
            ) : (
              <button onClick={turnOnAlerts}>Alert me if a starter is ruled out</button>
            )}
          </div>
        </section>
      )}
    </main>
  );
}

function Row({ slot, player, max }: { slot: string; player: Player | null; max: number }) {
  const out = ["Out", "IR", "Doubtful", "Sus"].includes(player?.injury_status ?? "");
  return (
    <li className="row">
      <span className="row__slot">{slot.replace("_", " ")}</span>
      {player ? (
        <>
          <span className="row__name">
            {player.name}
            <small>
              {player.position} {player.team ?? "FA"}
              {player.projection?.source === "bye" ? (
                <em className="tag tag--out">Bye</em>
              ) : (
                player.injury_status && <em className={out ? "tag tag--out" : "tag"}>{player.injury_status}</em>
              )}
            </small>
          </span>
          <RangeBar projection={player.projection} score={player.score} max={max} out={out} />
          <span className="row__score">{(player.score ?? 0).toFixed(1)}</span>
        </>
      ) : (
        <span className="row__name row__name--empty">Nobody eligible. Check waivers.</span>
      )}
    </li>
  );
}

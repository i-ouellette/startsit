export const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

export type Projection = { floor: number; median: number; ceiling: number; source: string };

export type Player = {
  player_id: string;
  name: string;
  position: string | null;
  eligible: string[];
  team: string | null;
  injury_status: string | null;
  projection: Projection | null;
  score: number | null;
};

export type League = {
  league_id: string;
  name: string;
  season: string;
  scoring: string;
  roster_positions: string[];
  total_rosters: number;
};

export type UserLeagues = {
  user_id: string;
  username: string;
  display_name: string | null;
  leagues: League[];
};

export type Swap = { slot: string; start: Player; sit: Player | null; gain: number };

export type Lineup = {
  league_id: string;
  owner_id: string;
  week: number;
  risk: number;
  scoring: string;
  lineup: { slot: string; player: Player | null }[];
  bench: Player[];
  swaps: Swap[];
  projected_total: number;
};

async function get<T>(path: string, signal?: AbortSignal): Promise<T> {
  const res = await fetch(`${API_URL}${path}`, { signal });
  if (!res.ok) {
    const body = await res.json().catch(() => ({}));
    throw new Error(body.detail ?? `Request failed (${res.status})`);
  }
  return res.json();
}

export const api = {
  leagues: (username: string) =>
    get<UserLeagues>(`/v1/users/${encodeURIComponent(username)}/leagues`),
  lineup: (leagueId: string, ownerId: string, risk: number, signal?: AbortSignal) =>
    get<Lineup>(
      `/v1/leagues/${leagueId}/lineup?owner_id=${ownerId}&risk=${risk.toFixed(2)}`,
      signal,
    ),
  subscribe: async (leagueId: string, ownerId: string, risk: number, email?: string) => {
    const res = await fetch(`${API_URL}/v1/alerts/subscriptions`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ league_id: leagueId, owner_id: ownerId, risk, email }),
    });
    if (!res.ok) throw new Error("Couldn't turn on alerts. Try again.");
    return res.json();
  },
};

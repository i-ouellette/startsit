import asyncio


def test_health(client):
    assert client.get("/health").json() == {"status": "ok"}


def test_user_leagues(client):
    r = client.get("/v1/users/isaac/leagues")
    assert r.status_code == 200
    body = r.json()
    assert body["user_id"] == "u1"
    assert body["leagues"][0]["scoring"] == "ppr"


def test_unknown_user_404(client):
    assert client.get("/v1/users/nobody/leagues").status_code == 404


def test_lineup_benches_injured_starter(client):
    r = client.get("/v1/leagues/L1/lineup", params={"owner_id": "u1", "week": 9})
    assert r.status_code == 200
    body = r.json()
    starters = {a["player"]["player_id"] for a in body["lineup"] if a["player"]}
    assert "rb2" not in starters  # Out -> benched
    assert "rb3" in starters  # handcuff fills in
    sat = {s["sit"]["player_id"] for s in body["swaps"] if s["sit"]}
    assert "rb2" in sat
    assert body["projected_total"] > 0


def test_risk_slider_changes_who_starts(client):
    def starters(risk):
        body = client.get(
            "/v1/leagues/L1/lineup", params={"owner_id": "u1", "week": 9, "risk": risk}
        ).json()
        return {a["player"]["player_id"] for a in body["lineup"] if a["player"]}

    # Steady possession WR when playing it safe, boom/bust deep threat when swinging big.
    safe, swing = starters(-1), starters(1)
    assert "wr4" in safe and "wr2" not in safe
    assert "wr2" in swing and "wr4" not in swing


def test_alert_job_suggests_swap(sleeper_mock):
    from app.clients.sleeper import SleeperClient
    from app.jobs.inactive_watch import run_once
    from app.jobs.notifier import ConsoleNotifier
    from app.models import AlertSubscriptionIn
    from app.services.projections import BaselineProjector
    from app.store import SubscriptionStore

    async def go():
        sleeper = SleeperClient()
        store = SubscriptionStore()
        store.add(AlertSubscriptionIn(league_id="L1", owner_id="u1", email="me@example.com"))
        notifier = ConsoleNotifier()
        first = await run_once(sleeper, BaselineProjector(sleeper), store, notifier)
        second = await run_once(sleeper, BaselineProjector(sleeper), store, notifier)
        await sleeper.aclose()
        return first, second, notifier

    first, second, notifier = asyncio.run(go())
    assert len(first) == 1 and first[0].player_name == "Hurt Back"
    assert first[0].swap_in is not None
    assert second == []  # deduped
    assert "Start" in notifier.outbox[0][2]


def test_alert_subscription_crud(client):
    created = client.post(
        "/v1/alerts/subscriptions", json={"league_id": "L1", "owner_id": "u1", "risk": 0.5}
    )
    assert created.status_code == 201
    sid = created.json()["id"]
    assert len(client.get("/v1/alerts/subscriptions").json()) == 1
    assert client.delete(f"/v1/alerts/subscriptions/{sid}").status_code == 204

from app.models import Projection
from app.services.optimizer import Candidate, optimize, starting_slots
from app.services.projections import distribution_from_samples, risk_score, scoring_format


def c(pid, pos, score):
    return Candidate(pid, frozenset([pos]), score)


def test_beats_greedy_when_flex_listed_first():
    # Greedy would put the RB in FLEX and leave the RB slot empty (total 10).
    result = optimize(["FLEX", "RB"], [c("rb", "RB", 10), c("wr", "WR", 9)])
    assert dict(result) == {"FLEX": "wr", "RB": "rb"}


def test_empty_slot_when_no_eligible_player():
    result = optimize(["QB", "K"], [c("qb", "QB", 20)])
    assert result == [("QB", "qb"), ("K", None)]


def test_superflex_takes_second_qb():
    result = optimize(
        ["QB", "SUPER_FLEX", "WR"],
        [c("qb1", "QB", 22), c("qb2", "QB", 17), c("wr1", "WR", 15), c("wr2", "WR", 12)],
    )
    assert dict(result) == {"QB": "qb1", "SUPER_FLEX": "qb2", "WR": "wr1"}


def test_starting_slots_drops_bench():
    assert starting_slots(["QB", "BN", "FLEX", "IR", "TAXI"]) == ["QB", "FLEX"]


def test_risk_score_endpoints():
    p = Projection(floor=5, median=12, ceiling=25)
    assert risk_score(p, 0) == 12
    assert risk_score(p, 1) == 25
    assert risk_score(p, -1) == 5
    assert risk_score(p, 0.5) == 18.5


def test_volatile_player_has_wider_range():
    steady = distribution_from_samples([12, 12, 13, 11], "WR")
    boom_bust = distribution_from_samples([2, 24, 3, 23], "WR")
    assert (boom_bust.ceiling - boom_bust.floor) > (steady.ceiling - steady.floor)
    assert steady.floor >= 0 and boom_bust.floor >= 0


def test_scoring_format():
    assert scoring_format({"rec": 1}) == "ppr"
    assert scoring_format({"rec": 0.5}) == "half_ppr"
    assert scoring_format({}) == "standard"

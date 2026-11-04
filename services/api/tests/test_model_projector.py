import asyncio
import json

from app.models import Projection
from app.services.projections import ModelProjector


class StubBaseline:
    def __init__(self):
        self.asked: list[str] = []

    async def project(self, player_ids, positions, season, week, scoring):
        self.asked += player_ids
        return {pid: Projection(floor=1, median=2, ceiling=3) for pid in player_ids}


def write_week(tmp_path, data):
    d = tmp_path / "projections"
    d.mkdir()
    (d / "2026_w10.json").write_text(json.dumps(data))


def run(proj, ids, scoring="ppr"):
    return asyncio.run(proj.project(ids, {}, 2026, 10, scoring))


def test_uses_model_bye_and_fallback(tmp_path):
    write_week(tmp_path, {"scorings": {"ppr": {"100": [4.0, 11.5, 22.0]}}, "bye": ["200"]})
    base = StubBaseline()
    out = run(ModelProjector(str(tmp_path), base), ["100", "200", "PHI"])
    assert out["100"].source == "model" and out["100"].ceiling == 22.0
    assert out["200"].source == "bye" and out["200"].median == 0
    assert out["PHI"].source == "baseline"  # defense not modeled
    assert base.asked == ["PHI"]


def test_no_file_or_scoring_falls_back(tmp_path):
    base = StubBaseline()
    out = run(ModelProjector(str(tmp_path), base), ["100"])
    assert out["100"].source == "baseline"

    write_week(tmp_path, {"scorings": {"ppr": {}}, "bye": []})
    out = run(ModelProjector(str(tmp_path), base), ["100"], scoring="standard")
    assert out["100"].source == "baseline"

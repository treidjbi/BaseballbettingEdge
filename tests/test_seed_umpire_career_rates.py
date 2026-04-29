import json
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from scripts.seed_umpire_career_rates import write_output


def test_write_output_preserves_delta_and_hp_games(tmp_path):
    agg = {
        "Mature Umpire": {"n": 75, "delta": 0.321},
        "Thin Umpire": {"n": 9, "delta": -0.4},
    }
    output_path = tmp_path / "career_k_rates.json"

    written = write_output(agg, min_games=10, output_path=output_path)

    assert written == {
        "Mature Umpire": {"delta": 0.321, "hp_games": 75},
    }
    stored = json.loads(output_path.read_text())
    assert stored["Mature Umpire"]["hp_games"] == 75

"""Preserved synthetic signed-score witnesses from b08284fd; no live I/O."""
import copy
import json
from pathlib import Path
import pytest
from market_infra import alternative_pick_evaluation_proof_v2 as proof

ROWS = json.loads((Path(__file__).parent / 'fixtures/signed_preclose_proof_review.json').read_text())

@pytest.mark.parametrize('name', sorted(ROWS))
def test_reviewed_signed_score_and_adversarial_rows(name):
    row = copy.deepcopy(ROWS[name])
    before = copy.deepcopy(row)
    valid, reasons = proof.validate_evaluation_proof_v2(proof=row['evaluation_proof'], row=row)
    assert valid is (name in {'negative', 'zero', 'positive'}), reasons
    assert row == before

@pytest.mark.parametrize('value', [float('nan'), float('inf'), -float('inf')])
def test_nonfinite_score_is_rejected(value):
    row = copy.deepcopy(ROWS['negative'])
    row['evaluation_proof']['preclose']['score'] = value
    assert not proof.validate_evaluation_proof_v2(proof=row['evaluation_proof'], row=row)[0]

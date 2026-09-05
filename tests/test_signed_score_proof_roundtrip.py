"""Regression witnesses from the preserved, independently reviewed proposal."""
from __future__ import annotations

import copy
import gzip
import json
from pathlib import Path
import runpy

import pytest

from market_infra import alternative_pick_evaluation_proof_v2 as proof
from market_infra.alternative_pick_selection_v2 import build_provisional_row_v2

ROOT = Path(__file__).resolve().parents[1]
ROWS = json.loads(gzip.decompress((ROOT / 'docs/research/evidence/2026-09-04-signed-score-proof-review/run/synthetic-rows.json.gz').read_bytes()))


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


@pytest.mark.parametrize('kwargs,expected', [
    (dict(edge=.21, probability=.65, adjusted_ev=.4), -1),
    (dict(agreement='neutral', edge=.21, probability=.44, adjusted_ev=.09), 0),
    ({}, 7),
])
def test_builder_and_serializer_preserve_signed_score(monkeypatch, kwargs, expected):
    build = runpy.run_path(str(ROOT / 'tests/forward_evidence_factory.py'))['build_case']
    serialized = []

    def capture(**inputs):
        built = proof.build_evaluation_proof_v2(**inputs)
        assert built.selection_safe, built.reason_codes
        assert built.proof['preclose']['score'] == expected
        row = build_provisional_row_v2(
            **inputs, proof_build=built,
            observed_at=inputs['evaluation'].normalized_inputs['observed_at'],
        )
        assert row is not None
        assert row['evaluation_proof'] == built.proof
        assert row['selection_status'] == 'not_selected'
        assert row['evaluation_proof']['preclose']['score'] == expected
        serialized.append(row)
        return built

    monkeypatch.setitem(build.__globals__, 'build_evaluation_proof_v2', capture)
    build(**kwargs)
    assert len(serialized) == 1

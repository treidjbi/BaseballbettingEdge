"""Compare an unapplied signed-score patch in memory. No network or writers.

--create makes a new review result directory; normal execution verifies it.
Production source files and old evidence are never modified.
"""
from __future__ import annotations
import argparse
import ast
from contextlib import contextmanager
import copy
import difflib
import gzip
import hashlib
import json
from pathlib import Path
import runpy
import subprocess
import sys

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]
sys.path.insert(0, str(ROOT))
from market_infra import alternative_pick_evaluation_proof_v2 as proof
from analytics.diagnostics import forward_pregame_evidence_validator as forward

PY_PATH = 'market_infra/alternative_pick_evaluation_proof_v2.py'
JS_PATH = 'netlify/functions/alternative-picks.mjs'


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def proposed_sources():
    original_py = (ROOT / PY_PATH).read_text()
    original_js = (ROOT / JS_PATH).read_text()
    old_py = '"reversal_book_count", "volatile_book_count", "score",\n'
    new_py = '"reversal_book_count", "volatile_book_count",\n'
    old_guard = 'if any(value is None or value < 0 for value in integers.values()):'
    new_guard = ('if (any(value is None or value < 0 for value in integers.values())\n'
                 '            or _integer(preclose.get("score")) is None):')
    old_js = "'reversal_book_count', 'volatile_book_count', 'score'];"
    new_js = "'reversal_book_count', 'volatile_book_count'];"
    old_js_guard = 'if (count < 2 || integers.some(field => integer(preclose[field]) == null || integer(preclose[field]) < 0)'
    new_js_guard = 'if (count < 2 || integer(preclose.score) == null\n      || integers.some(field => integer(preclose[field]) == null || integer(preclose[field]) < 0)'
    for text, token in [(original_py, old_py), (original_py, old_guard), (original_js, old_js), (original_js, old_js_guard)]:
        assert text.count(token) == 1, 'Review source drift: re-review the proposal'
    return original_py, original_py.replace(old_py, new_py).replace(old_guard, new_guard), original_js, original_js.replace(old_js, new_js).replace(old_js_guard, new_js_guard)


@contextmanager
def isolated_python(proposed):
    # Compile only the proposed shape helper. All scorer/semantic checks remain
    # the existing implementation, and the original helper is restored on exit.
    fn = next(n for n in ast.parse(proposed).body if isinstance(n, ast.FunctionDef) and n.name == '_preclose_state_valid')
    namespace = dict(proof.__dict__)
    exec(compile(ast.Module(body=[fn], type_ignores=[]), '<unapplied-review-helper>', 'exec'), namespace)
    original = proof._preclose_state_valid
    proof._preclose_state_valid = namespace['_preclose_state_valid']
    try:
        yield
    finally:
        proof._preclose_state_valid = original


def classify(rows):
    return {name: dict(valid=proof.validate_evaluation_proof_v2(proof=row['evaluation_proof'], row=row)[0],
                       reasons=list(proof.validate_evaluation_proof_v2(proof=row['evaluation_proof'], row=row)[1]))
            for name, row in rows.items()}


def run():
    originals = {str(p.relative_to(ROOT)): sha(p) for p in [ROOT/PY_PATH, ROOT/JS_PATH]}
    py, patched_py, js, patched_js = proposed_sources()
    patch = ''.join(difflib.unified_diff(py.splitlines(True), patched_py.splitlines(True), fromfile='a/'+PY_PATH, tofile='b/'+PY_PATH))
    patch += ''.join(difflib.unified_diff(js.splitlines(True), patched_js.splitlines(True), fromfile='a/'+JS_PATH, tofile='b/'+JS_PATH))
    build = runpy.run_path(str(ROOT/'tests/forward_evidence_factory.py'))['build_case']
    configurations = {
        'negative': dict(edge=.21, probability=.65, adjusted_ev=.4),
        'zero': dict(agreement='neutral', edge=.21, probability=.44, adjusted_ev=.09),
        'positive': {},
    }
    baseline_packets = {name: build(**kw, allow_pending=True) for name, kw in configurations.items()}
    with isolated_python(patched_py):
        packets = {name: build(**kw) for name, kw in configurations.items()}
        forward_reports = {name: forward.validate_packet(packet) for name, packet in packets.items()}
    rows = {name: packet['envelopes'][0]['frozen'] for name, packet in packets.items()}
    assert [rows[n]['evaluation_proof']['preclose']['score'] for n in configurations] == [-1, 0, 7]
    assert baseline_packets['negative']['envelopes'][0]['frozen']['evaluation_proof']['decision']['reason_codes'] == ['evaluation_proof_invalid']
    for name in ['zero', 'positive']:
        assert packets[name] == baseline_packets[name], 'Existing representable proof changed'
    assert rows['negative']['evaluation_proof']['preclose']['label'] == 'weak_preclose_clv_proxy'
    assert all(r['formal_prospective_credit'] == 0 for r in forward_reports.values())
    for field in ['qualifying_observation_count', 'book_count', 'toward_pick_count', 'away_from_pick_count', 'reversal_book_count', 'volatile_book_count', 'score']:
        values = {'negative': -1, 'missing': None, 'boolean': True, 'fractional': 1.25, 'nonnumeric': 'invalid'}
        if field == 'score':
            values = dict(missing=None, boolean=True, fractional=-1.25, nonnumeric='invalid', wrong_signed=-2, wrong_zero=0, wrong_positive=5, numeric_string='-1')
        for label, value in values.items():
            row = copy.deepcopy(rows['negative']); row['evaluation_proof']['preclose'][field] = value
            rows[field+'_'+label] = row
    for field, value in [('label', 'strong_preclose_clv_proxy'), ('freshness_status', 'pending'), ('reason_codes', ['invented']), ('risk_reasons', []), ('positive_reasons', []), ('last_observed_at', '2026-09-06T19:00:00+00:00')]:
        row = copy.deepcopy(rows['negative']); row['evaluation_proof']['preclose'][field] = value
        assert row != rows['negative'], field
        rows['tampered_'+field] = row
    baseline = classify(rows)
    baseline_nonfinite = {}
    for name, value in [('nan', float('nan')), ('positive_infinity', float('inf')), ('negative_infinity', -float('inf'))]:
        row = copy.deepcopy(rows['negative']); row['evaluation_proof']['preclose']['score'] = value
        baseline_nonfinite[name] = classify({name: row})[name]
    with isolated_python(patched_py):
        proposed = classify(rows)
        nonfinite = {}
        for name, value in [('nan', float('nan')), ('positive_infinity', float('inf')), ('negative_infinity', -float('inf'))]:
            row = copy.deepcopy(rows['negative']); row['evaluation_proof']['preclose']['score'] = value
            nonfinite[name] = classify({name: row})[name]
    js_result = json.loads(subprocess.run(['node', str(HERE/'compare-readers.mjs')], input=json.dumps(dict(baseline_source=js, proposed_source=patched_js, rows=rows)), text=True, capture_output=True, check=True).stdout)
    for name in rows:
        expected_before = name in {'zero', 'positive'}
        expected_after = name in configurations
        assert baseline[name]['valid'] == expected_before, (name, baseline[name])
        assert proposed[name]['valid'] == expected_after, (name, proposed[name])
        assert js_result['results'][name] == dict(baseline=expected_before, proposed=expected_after), (name, js_result['results'][name])
    assert all(not r['valid'] for r in nonfinite.values())
    assert all(not r['valid'] for r in baseline_nonfinite.values())
    assert all(r == dict(baseline=False, proposed=False) for r in js_result['nonfinite'].values())
    source = ROOT/'docs/research/evidence/2026-09-04-decision-time-adapter/frozen-source.json.gz'
    captured = json.loads(gzip.decompress(source.read_bytes()))
    old_rows = {str(i): row for i, row in enumerate(captured['rows'])}
    old_baseline = classify(old_rows)
    with isolated_python(patched_py):
        old_proposed = classify(old_rows)
        old_forward = forward.validate_packet(dict(records=captured['rows']))
    assert old_baseline == old_proposed
    assert len(old_rows) == 327 and all(r['valid'] for r in old_baseline.values())
    assert all(r['evaluation_proof']['preclose']['freshness_status'] == 'pending' for r in old_rows.values())
    assert old_forward['summary']['legacy_rows_rejected'] == 327 and old_forward['formal_prospective_credit'] == 0
    # Re-run the prior packet after restoring the original helper, without
    # writing or updating any prior acceptance record or dependency hash.
    previous = runpy.run_path(str(ROOT/'docs/research/evidence/2026-09-04-forward-evidence-validator/reproduce.py'))['verify']()
    assert originals == {p: sha(ROOT/p) for p in originals}
    return dict(
        mode='unapplied_counterfactual_format_review', production_changed=False,
        formal_prospective_credit=0, real_capture_active=False,
        proposal_sha256=hashlib.sha256(patch.encode()).hexdigest(), source_sha256=originals,
        historical_source_sha256=sha(source), shared_json_cases=len(rows),
        invalid_shared_cases=len(rows)-3, python_baseline=baseline, python_proposed=proposed,
        javascript=js_result, python_nonfinite=nonfinite, python_baseline_nonfinite=baseline_nonfinite,
        score_roundtrips={name: dict(score=rows[name]['evaluation_proof']['preclose']['score'], label=rows[name]['evaluation_proof']['preclose']['label'], decision=rows[name]['evaluation_proof']['decision'], forward_summary=forward_reports[name]['summary']) for name in configurations},
        historical=dict(rows=327, valid_before=327, valid_after=327, preclose_pending=327, credit=0),
        prior_acceptance=dict(case_count=previous['case_count'], accepted_input_cases=previous['accepted_input_cases'], formal_prospective_credit=previous['formal_prospective_credit']),
    ), patch, rows


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--create', action='store_true')
    args = parser.parse_args()
    result, patch, rows = run()
    if args.create:
        dest = HERE/'run'; dest.mkdir(exist_ok=False)
        (dest/'acceptance.json').write_text(json.dumps(result, sort_keys=True, indent=2)+'\n')
        (dest/'proposed.patch').write_text(patch)
        (dest/'synthetic-rows.json.gz').write_bytes(gzip.compress(forward.canonical(rows), mtime=0))
    else:
        assert result == json.loads((HERE/'run/acceptance.json').read_text())
        assert patch == (HERE/'run/proposed.patch').read_text()
        assert rows == json.loads(gzip.decompress((HERE/'run/synthetic-rows.json.gz').read_bytes()))
    print(json.dumps({k: result[k] for k in ['mode', 'shared_json_cases', 'invalid_shared_cases', 'historical', 'prior_acceptance', 'formal_prospective_credit', 'production_changed']}, indent=2))

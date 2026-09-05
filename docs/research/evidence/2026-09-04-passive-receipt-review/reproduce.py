"""Offline timing-boundary review; uses existing synthetic fixtures and validators."""
from pathlib import Path
import hashlib
import json
import runpy
import subprocess
import sys

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]
sys.path.insert(0, str(ROOT))
from analytics.diagnostics import forward_capture_feasibility as capture
from analytics.diagnostics import forward_pregame_evidence_validator as validator

BASE = '9a1c81c1'
SOURCES = {
    'scripts/build_live_events_to_supabase.py': [[953, 976], [1660, 1700], [1749, 1755], [1932, 1988]],
    'market_infra/operational_locks.py': [[172, 179]],
    'market_infra/alternative_pick_recording_v2.py': [[414, 441], [487, 540], [565, 579]],
    'market_infra/alternative_pick_preclose_v2.py': [[944, 952], [996, 1018]],
    'scripts/shadow_therundown_mainline_to_supabase.py': [[335, 350], [404, 408]],
    'market_infra/supabase_writer.py': [[146, 155]],
    'pipeline/fetch_results.py': [[272, 296], [355, 362], [407, 414], [697, 720]],
    'pipeline/run_pipeline.py': [[1099, 1110], [1160, 1185], [2196, 2206], [2227, 2228]],
    'scripts/run_render_pipeline_mode.py': [[367, 400]],
    'analytics/diagnostics/forward_pregame_evidence_validator.py': [[149, 155], [280, 313]],
    'analytics/diagnostics/forward_capture_feasibility.py': [[1, 79]],
    'tests/forward_capture_factory.py': [[1, 29]],
    'tests/forward_evidence_factory.py': [],
    'docs/superpowers/specs/2026-09-04-forward-pregame-evidence-contract.md': [[61, 84]],
}


def review():
    sources = {}
    for name, ranges in SOURCES.items():
        raw = (ROOT / name).read_bytes()
        old = subprocess.run(['git', 'show', BASE + ':' + name], cwd=ROOT,
                             check=True, capture_output=True).stdout
        assert raw == old, 'Reviewed source drift: ' + name
        sources[name] = dict(sha256=hashlib.sha256(raw).hexdigest(), line_ranges=ranges)
    factory = runpy.run_path(str(ROOT / 'tests/forward_capture_factory.py'))
    make = factory['source_bundle']
    cases = {'internally_valid_control': make()}
    expected = {'internally_valid_control': None}
    # Only acquisition time changes. Event times, bodies and frozen proof stay exact.
    for field, reason in [('snapshots', 'snapshot'), ('current_lines', 'current_lines'),
                          ('heartbeats', 'heartbeat'), ('windows', 'window'), ('read', 'read')]:
        bundle = make()
        item = bundle['captures'][0]['market_proof'][field]
        receipt = item[0] if isinstance(item, list) else item
        receipt['acquired_at'] = '2026-09-06T20:11:00+00:00'
        name = 'late_' + field
        cases[name] = bundle
        expected[name] = reason + '_receipt_after_lock'
    bundle = make()
    bundle['attachments'] = [a for a in bundle['attachments'] if a['kind'] != 'seed']
    cases['missing_seed'] = bundle
    expected['missing_seed'] = 'missing_seed'
    bundle = make()
    seed = next(a for a in bundle['attachments'] if a['kind'] == 'seed')
    body = validator.decode_receipt(seed['receipt'])
    body['recovery_status'] = 'recovered'
    seed['receipt'] = factory['factory']['receipt'](body, '2026-09-06T20:12:00+00:00', name='seed')
    cases['recovered_seed'] = bundle
    expected['recovered_seed'] = 'seed_not_original'
    results = {}
    for name, bundle in cases.items():
        report, packet = capture.assess(bundle)
        summary = report['summary']
        assert summary['opportunities'] == 1
        assert summary['internally_complete_inputs'] == int(expected[name] is None), (name, summary)
        if expected[name]:
            assert summary['exclusions'].get(expected[name]) == 1, (name, summary)
        assert report['formal_prospective_credit'] == 0 and not report['trusted_live_feasible']
        assert all(value is None for value in packet['manifest']['activation'].values())
        results[name] = summary
    return dict(source_commit=BASE, evidence_kind='synthetic_and_static_source_review',
                sources=sources, cases=results, case_count=len(cases), formal_credit=0,
                trusted_live_feasible=False, production_invoked=False,
                conclusion='passive_end_of_cycle_receipts_do_not_resolve_by_lock_eligibility')


if __name__ == '__main__':
    result = review()
    path = HERE / 'review.json'
    if sys.argv[1:] == ['--create']:
        with path.open('x') as stream:
            stream.write(json.dumps(result, indent=2, sort_keys=True) + '\n')
    else:
        assert not sys.argv[1:]
        assert result == json.loads(path.read_text())
    print(json.dumps(dict(cases=result['case_count'], formal_credit=0,
                         trusted_live_feasible=False, conclusion=result['conclusion'])))

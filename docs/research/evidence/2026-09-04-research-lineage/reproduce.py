"""Offline lineage diagnosis. Does not alter canonical Gate C or production.

Rebuilds only the captured August 15-September 3 research window. The lock
bridge is a counterfactual schema preview, not formal prospective credit.
"""
from __future__ import annotations
import gzip
import hashlib
import json
import sys
import tempfile
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]
sys.path.insert(0, str(ROOT))
from analytics.diagnostics import pitcher_k_outcome_dataset as dataset
from analytics.diagnostics import market_agreement_tracker as tracker
from analytics.diagnostics import selective_lean_prospective_audit as lean
from pipeline.name_utils import normalize


def load(name):
    path = HERE / name
    data = gzip.decompress(path.read_bytes()) if name.endswith('.gz') else path.read_bytes()
    return json.loads(data)


def save(name, data):
    (HERE / name).write_text(json.dumps(data, indent=2, sort_keys=True) + '\n')


def timestamp(value):
    return datetime.fromisoformat(str(value).replace('Z', '+00:00'))


def key(row):
    return (row.get('slate_date') or row.get('date'), normalize(row.get('pitcher') or row.get('normalized_pitcher')), str(row.get('side')).lower())


def book(value):
    return ''.join(c for c in str(value).lower() if c.isalnum())


def sha(data):
    return hashlib.sha256(data).hexdigest()


def main():
    # Preserve original bytes; reproduce Windows newline serialization in memory.
    canonical = ROOT / 'data/research/gate_c'
    manifest = json.loads((canonical / 'pitcher_k_outcome_dataset_manifest.json').read_text())
    old = (canonical / 'pitcher_k_outcome_dataset.jsonl').read_bytes()
    summary_bytes = (canonical / 'pitcher_k_outcome_dataset_summary.md').read_bytes()
    assert b'\r\n' not in old
    crlf = old.replace(b'\n', b'\r\n')
    assert sha(crlf) == manifest['jsonl_sha256']
    old_rows = [json.loads(line) for line in old.splitlines()]
    assert len(old_rows) == manifest['row_count'] == 2070
    assert old_rows == [json.loads(line) for line in crlf.splitlines()]
    provenance = dict(lf_sha256=sha(old), reconstructed_windows_crlf_sha256=sha(crlf),
                      manifest_sha256=manifest['jsonl_sha256'], rows=len(old_rows),
                      row_values_identical=True, source_window=manifest['source'],
                      summary_lf_sha256=sha(summary_bytes), summary_crlf_sha256=sha(summary_bytes.replace(b'\n', b'\r\n')),
                      manifest_summary_sha256=manifest['summary_sha256'])

    source = load('compact-and-lock-source.json.gz')
    served = load('served-artifacts.json.gz')
    history = next(r['payload'] for r in served if r['key'] == 'history')
    archives = [r for r in served if r['key'] != 'history']
    assert len(archives) == 20
    assert len(source['market_pick_evidence']) < 2001 and len(source['live_market_display_state']) < 2001
    locks = defaultdict(list)
    for row in source['locks']:
        locks[key(row)].append(row)
    assert all(len(v) == 1 for v in locks.values())
    with tempfile.TemporaryDirectory(prefix='bbe-research-lineage-') as tmp:
        temp = Path(tmp)
        for ar in archives:
            (temp / (ar['key'] + '.json')).write_text(json.dumps(ar['payload']))
        hp = temp / 'history.json'
        hp.write_text(json.dumps(history))
        tr = tracker.build_tracker_rows(market_pick_evidence_rows=source['market_pick_evidence'],
            live_market_display_rows=source['live_market_display_state'], market_snapshot_rows=[], history_rows=history)
        tp, dp = temp / 'tracker.json', temp / 'display.json'
        tp.write_text(json.dumps(tr))
        dp.write_text(json.dumps(source['live_market_display_state']))
        diagnostics = {}
        rows = dataset.build_dataset(archive_dir=temp, start_date='2026-08-15', end_date='2026-09-03',
            lineup_handedness_backfill_path=temp / 'no_handedness_backfill.json',
            actual_opportunity_backfill_path=temp / 'no_opportunity_backfill.json',
            market_agreement_tracker_path=tp, live_market_display_path=dp,
            picks_history_path=hp, diagnostics=diagnostics)
        # The loader's logical archive path is retained; add separate captured-source lineage.
        for row in rows:
            row['review_captured_source_url'] = next(r['url'] for r in archives if r['key'] == row['slate_date'])
        reconciliation = dataset.reconcile_picks_history(rows, start_date='2026-08-15', end_date='2026-09-03',
            history_path=hp, included_slate_dates=sorted({r['slate_date'] for r in rows}))
    assert len({r['dataset_key'] for r in rows}) == len(rows)
    assert not [r['dataset_key'] for r in rows if dataset.validate_dataset_row(r)]
    (HERE / 'bounded-gate-c.jsonl.gz').write_bytes(gzip.compress(('\n'.join(json.dumps(r,sort_keys=True) for r in rows)+'\n').encode(),mtime=0))
    tracked = [r for r in rows if r.get('is_tracked_pick') and r.get('result') in ('win', 'loss')]
    matched, exclusions, candidates = [], [], []
    for row in tracked:
        group = locks.get(key(row), [])
        reasons = []
        lock = group[0] if len(group) == 1 else None
        if not lock:
            reasons.append('missing_or_ambiguous_operational_lock')
        else:
            if not lock.get('consumed_at'):
                reasons.append('unconsumed_lock')
            for left, right in [('bet_time_line','locked_k_line'),('bet_time_odds','locked_odds'),('display_verdict','locked_verdict')]:
                if row.get(left) != lock.get(right): reasons.append(left + '_mismatch')
            for left, right in [('bet_time_at','locked_at'),('game_time','game_time')]:
                if not row.get(left) or timestamp(row[left]) != timestamp(lock[right]): reasons.append(left + '_mismatch')
            if book(row.get('bet_time_book')) != book(lock.get('locked_book')): reasons.append('bet_time_book_mismatch')
            if timestamp(lock['locked_at']) >= timestamp(lock['game_time']): reasons.append('poststart_lock')
            if not lock.get('source_artifact_path') or len(lock.get('source_artifact_sha256','')) != 64: reasons.append('missing_lock_artifact_provenance')
        preview = dict(row)
        if not reasons:
            preview.update(operational_lock_id=lock['id'], operational_lock_consumed_at=lock['consumed_at'],
                operational_lock_source_artifact_path=lock['source_artifact_path'],
                operational_lock_source_artifact_sha256=lock['source_artifact_sha256'])
            matched.append(key(row))
        else:
            exclusions.append(dict(identity=key(row), reasons=reasons,
                gate_c_bet_time_book=row.get('bet_time_book'), operational_lock_book=lock.get('locked_book') if lock else None))
        if lean.selector_matches(row):
            missing_before = lean.missing_critical_inputs(row)
            missing_after = lean.missing_critical_inputs(preview)
            candidates.append(dict(identity=key(row), dataset_key=row['dataset_key'],
                selector_fingerprint=lean.RULE_FINGERPRINT, lock_join_reasons=reasons,
                missing_before=missing_before, missing_after_lock_only_preview=missing_after,
                archive_line=row['k_line'], locked_line=row.get('bet_time_line'),
                archive_outcome_source=row.get('archive_outcome_reconciliation_source'),
                provider=row.get('provider'), official_provider=row.get('official_line_source_provider'),
                agreement=row.get('market_agreement_label'), timing=row.get('bet_timing_window'),
                quote_differs_from_lock=row['k_line'] != row.get('bet_time_line'),
                result=row['result'], diagnostic_pnl=row.get('pick_history_pnl'),
                would_pass_missing_inputs_only=not missing_after,
                formal_prospective_credit=False))
    before = Counter(m for c in candidates for m in c['missing_before'])
    after = Counter(m for c in candidates for m in c['missing_after_lock_only_preview'])
    frozen_candidates = load('frozen-candidate-proof.json')['rows']
    frozen_keys = {key(r) for r in frozen_candidates}
    archive_keys = {tuple(r['identity']) for r in candidates}
    frozen_comparison = dict(frozen_rule_matches=len(frozen_candidates), archive_rule_matches=len(candidates),
        overlap=len(frozen_keys & archive_keys), frozen_only=sorted(frozen_keys - archive_keys),
        archive_only=sorted(archive_keys - frozen_keys),
        preclose_labels=dict(Counter(str(r['evaluation_proof']['preclose']['label']) for r in frozen_candidates)),
        preclose_freshness=dict(Counter(str(r['evaluation_proof']['preclose']['freshness_status']) for r in frozen_candidates)),
        preclose_reason_codes=dict(Counter(reason for r in frozen_candidates for reason in r['evaluation_proof']['preclose']['reason_codes'])))
    source_presence = {}
    for group, data in [('canonical_historical_gate_c',old_rows),('bounded_current_gate_c',rows),('bounded_history',history),('operational_locks',source['locks'])]:
        source_presence[group] = dict(rows=len(data), fields={f:sum(r.get(f) is not None for r in data) for f in
            ['operational_lock_id','operational_lock_consumed_at','operational_lock_source_artifact_path','consumed_at','source_artifact_sha256','preclose_clv_proxy_label','market_agreement_label','official_line_source_provider']})
    hist_locked = {key(r):r for r in history if r.get('locked_at') and r.get('result') in ('win','loss','void')}
    consumption = dict(operational_locks=len(source['locks']), consumed=sum(bool(r['consumed_at']) for r in source['locks']),
        closed_locked_history=len(hist_locked), missing_history=[dict(identity=k,consumed_at=v[0]['consumed_at']) for k,v in locks.items() if k not in hist_locked])
    transport = load('transport-sample.json')
    direct = json.loads(transport['payload_text'])
    api = next(r['payload'] for r in archives if r['key']=='2026-08-30')
    assert direct == api
    result = dict(scope='Bounded offline reconstruction and counterfactual schema preview; not a hosted-run certification or eligibility promotion',
        gate_c_provenance=provenance, source_capture=source['captured_at'],
        source_presence=source_presence, compact_counts=dict(evidence=len(source['market_pick_evidence']),display=len(source['live_market_display_state']),derived_tracker=len(tr)),
        rebuild=dict(rows=len(rows),tracked_graded=len(tracked),dates=len({r['slate_date'] for r in rows}),duplicates=0,reconciliation=reconciliation,diagnostics=diagnostics),
        consumption=consumption, lock_join=dict(exact_matches=len(matched),exclusions=exclusions),
        selective_lean=dict(fingerprint=lean.RULE_FINGERPRINT,matched_candidates=len(candidates),missing_before=dict(before),missing_after_lock_only_preview=dict(after),frozen_comparison=frozen_comparison,
            pass_missing_inputs_before=sum(not c['missing_before'] for c in candidates),pass_missing_inputs_after_lock_only=sum(not c['missing_after_lock_only_preview'] for c in candidates),
            formal_credit_granted=0,candidates=candidates),
        transport=dict(served_hash_mismatch_dates=[r['key'] for r in archives if not r['expected_hash_match']],
                       august30_sql_and_served_values_equal=True,
                       note='Stored issuer hash is not a cross-serialization byte checksum. Do not certify all dated payload hashes from served JSON.'))
    save('analysis.json',result)
    print(json.dumps(dict(rebuild=result['rebuild'],consumption=consumption,exact_lock_matches=len(matched),join_exclusion_counts=dict(Counter(reason for r in exclusions for reason in r['reasons']))),indent=2))
    print('Candidate gaps:',json.dumps({k:v for k,v in result['selective_lean'].items() if k!='candidates'},indent=2))


if __name__ == '__main__':
    main()

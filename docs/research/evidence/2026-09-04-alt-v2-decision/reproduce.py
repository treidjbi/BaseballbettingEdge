"""Offline September 4 decision analysis. Reads only these captured exports.

Run from any directory with the repository's .venv/bin/python. This writes
derived files in this evidence directory only; no network or production IO.
"""
from __future__ import annotations

import hashlib
import json
import sys
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]
sys.path.insert(0, str(ROOT))
from pipeline.name_utils import normalize
from market_infra.alternative_pick_evaluation_proof_v2 import validate_evaluation_proof_v2
from analytics.diagnostics.clv_official_close_packet import build_close_packet
from analytics.diagnostics.clv_process_target_validation import classify_final_clv

FINGERPRINT = '23bacff0fa923685ae52c5a9cfbadfb9f5902fb64d91759cfe9b4b1169a221c4'
INPUTS = ['selected-lock-proofs.json', 'bounded-history.json',
          'comparison-universe.json', 'archive-context.json', 'bounded-close-snapshots.json']


def read(name):
    return json.loads((HERE / name).read_text())


def write(name, value):
    (HERE / name).write_text(json.dumps(value, indent=2, sort_keys=True) + '\n')


def timestamp(value):
    return datetime.fromisoformat(value.replace('Z', '+00:00'))


def key(row):
    return (row.get('slate_date', row.get('date')), normalize(row['pitcher']), row['side'].lower())


def indexed(rows):
    result = {key(r): r for r in rows}
    assert len(result) == len(rows), 'duplicate identity'
    return result


def flat_profit(result, odds):
    assert result in ('win', 'loss', 'void') and odds and abs(odds) >= 100
    return (odds / 100 if odds > 0 else 100 / -odds) if result == 'win' else -1.0 if result == 'loss' else 0.0


def score(rows, weighted=False):
    active = [r for r in rows if not weighted or r['stake'] > 0]
    units = sum((r['stake'] if weighted else 1) for r in active if r['result'] != 'void')
    pnl = sum(r['flat_pnl'] * (r['stake'] if weighted else 1) for r in active)
    counts = Counter(r['result'] for r in active)
    return dict(rows=len(active), wins=counts['win'], losses=counts['loss'], voids=counts['void'],
                settled_risk_units=units, pnl=round(pnl, 6),
                roi_pct=round(100 * pnl / units, 4) if units else None,
                slate_dates=len({r['date'] for r in active}), pitchers=len({r['pitcher'] for r in active}))


def group_scores(rows, field):
    groups = defaultdict(list)
    for row in rows:
        groups[str(row.get(field, 'unknown'))].append(row)
    return {k: score(v) for k, v in sorted(groups.items())}


def main():
    selected = read(INPUTS[0])['rows']
    history_source = read(INPUTS[1])
    universe = read(INPUTS[2])
    archive_source = read(INPUTS[3])
    raw_close = read(INPUTS[4])
    hist_all = indexed(history_source['rows'])
    hist = indexed([r for r in history_source['rows'] if r.get('locked_at') and r.get('result') in ('win', 'loss', 'void')])
    locks = indexed(universe['locks'])
    frozen = indexed(universe['frozen'])
    assert frozen.keys() <= locks.keys()
    selected_by_key = indexed([r['alt'] for r in selected])
    archive = {}
    for artifact in archive_source['artifacts']:
        date = artifact['artifact_key'].split(':')[1]
        for pitcher in artifact['pitchers']:
            archive_key = (date, normalize(pitcher['pitcher']), timestamp(pitcher['game_time']))
            assert archive_key not in archive
            archive[archive_key] = pitcher
    proof_failures = []
    for row in selected:
        alt, lock = row['alt'], row['lock']
        valid, reasons = validate_evaluation_proof_v2(proof=alt['evaluation_proof'], row=alt)
        if not valid:
            proof_failures.append(dict(id=alt['id'], reasons=reasons))
        assert alt['selector_fingerprint'] == FINGERPRINT
        assert alt['checkpoint'] == 'frozen_pregame' and alt['selection_status'] == 'selected'
        assert timestamp(alt['frozen_at']) < timestamp(alt['game_time'])
        assert timestamp(alt['inserted_at']) < timestamp(alt['game_time'])
        assert timestamp(alt['frozen_at']) == timestamp(lock['locked_at'])
        assert key(alt) == key(lock) and lock['consumed_at']
        assert timestamp(alt['locked_at']) == timestamp(lock['locked_at'])
        assert alt['model_k_line'] == lock['locked_k_line'] and alt['official_odds'] == lock['locked_odds']
        assert alt['official_verdict'] == lock['locked_verdict']
        assert alt['lock_artifact_sha256'] == lock['source_artifact_sha256']
        assert key(alt) in hist
    assert not proof_failures
    assert len(selected) == len(selected_by_key) == 113

    snapshots = {}
    for row in raw_close['rows']:
        assert len(row['snapshots'] or []) < 101, 'snapshot export capped'
        for snap in row['snapshots'] or []:
            if snap['id'] in snapshots:
                assert snap == snapshots[snap['id']]
            snapshots[snap['id']] = snap
    official = [{**r['alt'], 'official_line_source_provider': r['alt']['evaluation_proof']['candidate']['line_source_provider']} for r in selected]
    close = build_close_packet([r['lock'] for r in selected], list(snapshots.values()),
                               official_rows=official, start_date='2026-07-24', end_date='2026-09-03',
                               generated_at=raw_close['captured_at'])
    close_labels = {}
    for r in close['packet_rows']:
        close_labels[key(r)] = classify_final_clv(dict(close_eligibility='eligible', side=r['side'],
            lock_line=r['lock_line'], close_line=r['line'], lock_odds=r['lock_odds'], close_odds=r['american_odds']))
    write('official-close-packet.json', close)

    mismatch = []
    archive_status = Counter()
    rows = []
    for ident, h in hist.items():
        l = locks.get(ident)
        f = frozen.get(ident, {})
        a = selected_by_key.get(ident, {})
        ni = f.get('normalized_inputs') or {}
        if l:
            assert l['consumed_at']
            for field in ('locked_odds', 'locked_k_line', 'locked_verdict'):
                if h.get(field) != l.get(field):
                    mismatch.append(dict(identity=ident, field=field, history=h.get(field), lock=l.get(field)))
            for field in ('game_time', 'locked_at'):
                if timestamp(h[field]) != timestamp(l[field]):
                    mismatch.append(dict(identity=ident, field=field, history=h.get(field), lock=l.get(field)))
        for hf, ff in [('locked_odds', 'official_odds'), ('locked_k_line', 'model_k_line'), ('locked_verdict', 'official_verdict')]:
            if f and h.get(hf) != f.get(ff):
                mismatch.append(dict(identity=ident, field='frozen_' + hf, history=h.get(hf), frozen=f.get(ff)))
        if f:
            assert timestamp(f['game_time']) == timestamp(h['game_time'])
            if ni.get('observed_at'):
                assert timestamp(ni['observed_at']) == timestamp(h['locked_at'])
        odds = h['locked_odds']
        pnl = flat_profit(h['result'], odds)
        # Stored history flat P&L is rounded; compare at that precision.
        if h.get('pnl') is not None:
            assert abs(h['pnl'] - pnl) < 0.001, (ident, h['pnl'], pnl)
        if h['result'] != 'void':
            actual, line = h['actual_ks'], h['locked_k_line']
            assert actual is not None and actual != line
            win = actual > line if h['side'].lower() == 'over' else actual < line
            assert win == (h['result'] == 'win')
        ar = archive.get((ident[0], ident[1], timestamp(h['game_time'])), {})
        matches = [t for t in (ar.get('tracked_picks') or [])
                   if t.get('side', '').lower() == ident[2] and t.get('locked_at')
                   and timestamp(t['locked_at']) == timestamp(h['locked_at'])
                   and t.get('locked_odds') == odds and t.get('locked_k_line') == h['locked_k_line']
                   and t.get('locked_verdict') == h['locked_verdict']]
        context_status = 'lock_consistent_archive' if len(matches) == 1 else 'unmatched_archive_context'
        archive_status[context_status] += 1
        path_b = 'unknown'
        if len(matches) == 1 and ar.get('batter_handedness_mode') == 'path_b':
            path_b = 'all_real_splits' if ar.get('lineup_real_split_count') == 9 and ar.get('lineup_path_a_fallback_count') == 0 else 'mixed_or_fallback_splits'
        verdict = h['locked_verdict']
        stake = {'FIRE 1u': 1, 'FIRE 2u': 2, 'LEAN': 0, 'PASS': 0}[verdict]
        row = dict(date=ident[0], pitcher=ident[1], side=ident[2], line=h['locked_k_line'],
            odds=odds, result=h['result'], actual_ks=h['actual_ks'], flat_pnl=pnl,
            stake=stake, official_verdict=verdict, lock_id=l.get('id') if l else None,
            alt_id=a.get('id'), lane=a.get('lane', 'not_selected'),
            v2_status=f.get('selection_status', 'no_frozen_v2'),
            price_sign='plus' if odds > 0 else 'minus',
            exact_provider=f.get('provider', 'unknown'),
            provider_posture=a.get('provider_posture') or (ar.get('market_source_mode', 'unknown') if len(matches) == 1 else 'unknown'),
            provider_posture_source='frozen_proof' if a else context_status,
            path_b=path_b, archive_context_status=context_status,
            quality=ni.get('quality_gate_level', 'unknown'),
            workload=ni.get('workload_input_status', 'unknown'),
            opportunity=ni.get('opportunity_bucket', 'unknown'),
            leash=ni.get('leash_risk_bucket', 'unknown'),
            archetype=ni.get('pitcher_archetype_bucket', 'unknown'),
            timing=ni.get('bet_timing_window', 'unknown'),
            model_market=ni.get('model_market_relationship', 'unknown'),
            book=l.get('locked_book', 'unknown') if l else 'unknown',
            final_clv=close_labels.get(ident, 'unknown' if a else 'not_requested'),
            lock_minutes_before_start=(timestamp(h['game_time']) - timestamp(h['locked_at'])).total_seconds() / 60)
        rows.append(row)
    assert not mismatch, mismatch[:10]
    mainline = [r for r in rows if r['stake'] > 0]
    alts = [r for r in rows if r['alt_id']]
    groups = dict(mainline_all_locked_flat=rows, mainline_fire_weighted=mainline,
                  mainline_fire_flat=mainline, common_v2_universe_flat=[r for r in rows if r['v2_status'] != 'no_frozen_v2'],
                  all_alt=alts, consensus_core=[r for r in alts if r['lane'] == 'consensus_core'],
                  reentry_expansion=[r for r in alts if r['lane'] == 'reentry_expansion'],
                  unselected_v2=[r for r in rows if r['v2_status'] == 'not_selected'],
                  pending_v2=[r for r in rows if r['v2_status'] == 'pending'],
                  no_frozen_v2=[r for r in rows if r['v2_status'] == 'no_frozen_v2'],
                  alt_mainline_overlap=[r for r in alts if r['stake'] > 0],
                  alt_incremental_lean=[r for r in alts if r['stake'] == 0],
                  mainline_fire_not_alt=[r for r in mainline if not r['alt_id']])
    summary = {k: score(v, weighted=k == 'mainline_fire_weighted') for k,v in groups.items()}
    fields = ['side', 'line', 'price_sign', 'official_verdict', 'exact_provider', 'provider_posture',
              'path_b', 'workload', 'opportunity', 'leash', 'archetype', 'quality', 'timing',
              'model_market', 'book', 'final_clv', 'v2_status']
    slices = {name: {field: group_scores(group, field) for field in fields}
              for name, group in groups.items() if name in ('mainline_all_locked_flat', 'mainline_fire_flat', 'all_alt', 'consensus_core', 'reentry_expansion')}
    dates = sorted({r['date'] for r in rows})
    assert len(dates) == 42
    rolling = []
    for i in range(len(dates) - 13):
        ds = set(dates[i:i+14])
        rolling.append(dict(start=dates[i], end=dates[i+13], scores={name: score([r for r in group if r['date'] in ds], name == 'mainline_fire_weighted')
                       for name,group in groups.items() if name in ('mainline_fire_weighted', 'mainline_all_locked_flat', 'all_alt', 'consensus_core', 'reentry_expansion')}))
    robustness = {}
    for name in ('all_alt', 'consensus_core', 'reentry_expansion'):
        group = groups[name]
        loso = [score([r for r in group if r['date'] != d])['pnl'] for d in dates]
        pitch = group_scores(group, 'pitcher')
        robustness[name] = dict(leave_one_slate_out_pnl_range=[min(loso), max(loso)],
            rolling_14_windows=len(rolling), positive_14_windows=sum(w['scores'][name]['pnl'] > 0 for w in rolling),
            max_pitcher_rows=max(v['rows'] for v in pitch.values()),
            unique_pitchers=len(pitch), lock_minutes_range=[min(r['lock_minutes_before_start'] for r in group), max(r['lock_minutes_before_start'] for r in group)],
            by_slate=group_scores(group, 'date'))
    missing = [dict(identity=k, lock_id=locks[k]['id'], verdict=locks[k]['locked_verdict'],
                    line=locks[k]['locked_k_line'], odds=locks[k]['locked_odds'],
                    frozen_status=frozen.get(k, {}).get('selection_status'), any_history=hist_all.get(k))
               for k in locks.keys() - hist.keys()]
    checks = dict(selected_proofs_valid=len(selected), selected_proof_failures=proof_failures,
                  selector_fingerprint=FINGERPRINT, history_rows=len(hist_all), closed_locked_history=len(hist),
                  operational_locks=len(locks), frozen_v2=len(frozen), frozen_status_counts=dict(Counter(r['selection_status'] for r in frozen.values())),
                  frozen_without_normalized_observed_at=sum(not (r.get('normalized_inputs') or {}).get('observed_at') for r in frozen.values()),
                  lock_history_frozen_mismatches=mismatch, history_without_operational_lock=[k for k in hist.keys() - locks.keys()],
                  missing_history=missing, archive_context_counts=dict(archive_status), raw_snapshots=len(snapshots),
                  snapshot_targets_without_rows=sum(not r['snapshots'] for r in raw_close['rows']),
                  close_manifest=close['manifest'], complete_window_slate_dates=dates,
                  source_hashes={name: hashlib.sha256((HERE/name).read_bytes()).hexdigest() for name in INPUTS},
                  history_artifact_sha256=history_source['sha256'])
    write('analysis.json', dict(checks=checks, summary=summary, slices=slices, robustness=robustness, rolling_14_slate_windows=rolling))
    write('row-level-analysis.json', rows)
    lines = ['# Alt V2 required slices', '', 'July 24–September 3, 2026. All tables use 1u risk at recorded locked odds; voids return stake.', '',
             'These are descriptive post-outcome partitions, never new selectors. Frozen inputs supply quality/workload/model-market/timing; Path B is later archive context with an exact tracked-lock match, not a frozen covariate. Mainline FIRE here is flat; the decision packet separately reports official 1u/2u exposure.', '']
    for field in fields:
        lines += ['## ' + field, '', '| Group | Slice | Rows | W–L–V | P&L u | ROI % | Dates |', '| --- | --- | ---: | --- | ---: | ---: | ---: |']
        for name in ('mainline_all_locked_flat', 'mainline_fire_flat', 'all_alt', 'consensus_core', 'reentry_expansion'):
            for val, s in slices[name][field].items():
                lines.append(f"| {name} | {val} | {s['rows']} | {s['wins']}–{s['losses']}–{s['voids']} | {s['pnl']:.3f} | {s['roi_pct']} | {s['slate_dates']} |")
        lines.append('')
    lines += ['## Complete 14-slate rolling windows', '', 'Common slate calendar includes zero-selection dates. Windows overlap and are not independent replications.', '',
              '| Start | End | Mainline FIRE weighted u | All tracked flat u | Alt u | Consensus u | Re-entry u |', '| --- | --- | ---: | ---: | ---: | ---: | ---: |']
    for w in rolling:
        vals = [f"{w['scores'][n]['pnl']:.3f}" for n in ('mainline_fire_weighted', 'mainline_all_locked_flat', 'all_alt', 'consensus_core', 'reentry_expansion')]
        lines.append('| ' + ' | '.join([w['start'], w['end']] + vals) + ' |')
    (HERE / 'required-slices.md').write_text('\n'.join(lines) + '\n')
    print(json.dumps(dict(summary=summary, checks=checks, robustness={k:{f:v for f,v in r.items() if f!='by_slate'} for k,r in robustness.items()}), indent=2))


if __name__ == '__main__':
    main()

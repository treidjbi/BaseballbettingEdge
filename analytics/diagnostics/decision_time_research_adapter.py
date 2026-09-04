"""Offline linkage evidence only; never a replacement Gate C dataset or credit ledger.

Run with ``python -m analytics.diagnostics.decision_time_research_adapter --help``.
No network, writes to canonical data, source repair, or prospective promotion.
"""
from __future__ import annotations

import argparse
from collections import Counter, defaultdict
import copy
from datetime import date, datetime
import gzip
import hashlib
import json
import math
from pathlib import Path
import re

from market_infra.alternative_pick_evaluation_proof_v2 import validate_evaluation_proof_v2
from analytics.diagnostics.selective_lean_prospective_audit import selector_matches
from pipeline.name_utils import normalize

ROOT = Path(__file__).resolve().parents[2]
BUNDLE = 'pregame_alternative_pick_methodology_v2'


def explicit_official_provider(fields):
    """A present but ambiguous authoritative field fails closed."""
    for field in ('official_line_source_provider', 'official_odds_source'):
        if field in fields and fields[field] not in (None, ''):
            value = str(fields[field]).strip().lower()
            return value if value in {'therundown', 'propline', 'theoddsapi'} else None
    return None


def _time(value):
    try:
        result = datetime.fromisoformat(value.replace('Z', '+00:00'))
        return result if result.tzinfo is not None else None
    except (AttributeError, TypeError, ValueError):
        return None


def _same_time(a, b):
    return _time(a) is not None and _time(a) == _time(b)


def _number(value):
    return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value)


def _same_number(a, b):
    return _number(a) and _number(b) and a == b


def _book(value):
    return re.sub(r'[^a-z0-9]', '', str(value or '').lower())


def _identity(row):
    if not isinstance(row, dict):
        raise ValueError('Source row must be an object')
    slate = date.fromisoformat(row.get('slate_date', ''))
    pitcher = normalize(row.get('normalized_pitcher') or row.get('pitcher') or '').strip()
    side = str(row.get('side') or '').lower().strip()
    if not pitcher or side not in {'over', 'under'}:
        raise ValueError('Malformed source identity')
    return slate.isoformat(), pitcher, side


def _index(rows, start, end, tracked_only=False):
    indexed = defaultdict(list)
    for row in rows:
        key = _identity(row)
        if start <= key[0] <= end and (not tracked_only or row.get('is_tracked_pick') is True):
            indexed[key].append(row)
    return indexed


def _record(key, sources, source_conflicts=()):
    reasons, gaps = list(source_conflicts), ['market_agreement_unavailable', 'frozen_path_b_unavailable']
    unique = {}
    for name, rows in sources.items():
        if len(rows) != 1:
            reasons.append(('missing_' if not rows else 'duplicate_') + name + ('' if not rows else '_identity'))
        unique[name] = rows[0] if len(rows) == 1 and f'duplicate_{name}_source_id' not in reasons else None
    archive, lock, frozen = (unique[x] for x in ('gate_c', 'lock', 'frozen'))
    decision, match, preclose, proof_errors = None, None, None, []
    frozen_errors = []
    if frozen:
        proof = frozen.get('evaluation_proof')
        valid, proof_errors = validate_evaluation_proof_v2(proof=proof, row=frozen)
        if not valid:
            frozen_errors.append('invalid_frozen_proof')
        if frozen.get('bundle_id') != BUNDLE:
            frozen_errors.append('wrong_frozen_bundle')
        if frozen.get('checkpoint') != 'frozen_pregame':
            frozen_errors.append('not_frozen_pregame')
        game, freeze, inserted = map(_time, (frozen.get('game_time'), frozen.get('frozen_at'), frozen.get('inserted_at')))
        if not (game and freeze and inserted and freeze < game and inserted < game and freeze <= inserted):
            frozen_errors.append('freeze_not_prospective')
        if not _same_time(frozen.get('frozen_at'), frozen.get('locked_at')):
            frozen_errors.append('freeze_lock_time_mismatch')
        generated = _time(frozen.get('source_artifact_generated_at'))
        if not (generated and freeze and generated <= freeze):
            frozen_errors.append('artifact_not_available_at_freeze')
        if lock:
            if not all(_same_time(frozen.get(a), lock.get(b)) for a, b in (
                ('game_time', 'game_time'), ('locked_at', 'locked_at'), ('observed_at', 'locked_at'))):
                frozen_errors.append('lock_frozen_time_mismatch')
            if not (all(_same_number(frozen.get(a), lock.get(b)) for a, b in (
                ('model_k_line', 'locked_k_line'), ('official_odds', 'locked_odds')))
                and frozen.get('official_verdict') == lock.get('locked_verdict')
                and _book(frozen.get('official_book')) and _book(frozen.get('official_book')) == _book(lock.get('locked_book'))):
                frozen_errors.append('lock_frozen_quote_mismatch')
            sha = frozen.get('lock_artifact_sha256')
            if not (isinstance(sha, str) and re.fullmatch('[0-9a-f]{64}', sha)
                    and sha == lock.get('source_artifact_sha256') == frozen.get('source_artifact_byte_sha256')):
                frozen_errors.append('lock_frozen_hash_mismatch')
        else:
            frozen_errors.append('frozen_lock_binding_unavailable')
        if valid:
            inputs = proof['normalized_inputs']
            provider = proof['candidate']['line_source_provider']
            binding = proof['bindings'].get(provider, {})
            if not (inputs.get('quality_gate_level') in {'clean', 'capped', 'blocked'}
                    and inputs.get('model_market_relationship') not in (None, '', 'unknown')
                    and inputs.get('line_bucket') and inputs.get('official_verdict')
                    and _number(inputs.get('edge'))
                    and _same_time(inputs.get('observed_at'), frozen.get('locked_at'))
                    and binding.get('role') == 'official'):
                frozen_errors.append('frozen_selector_inputs_unavailable')
            evidence = proof['preclose']
            if evidence.get('freshness_status') == 'fresh':
                first, last = _time(evidence.get('first_observed_at')), _time(evidence.get('last_observed_at'))
                if not (first and last and freeze and game and first <= last <= freeze < game
                        and evidence.get('label') and evidence.get('qualifying_observation_count', 0) >= 2):
                    frozen_errors.append('preclose_not_prospective')
                else:
                    preclose = copy.deepcopy(evidence)
            if not frozen_errors:
                decision = copy.deepcopy(inputs)
                decision['official_line_source_provider'] = provider
                match = selector_matches(dict(inputs, display_verdict=inputs['official_verdict']))
    reasons.extend(frozen_errors)
    if frozen_errors:
        preclose = None
    if preclose is None:
        gaps.append('preclose_unavailable')
    if lock:
        consumed, locked, game = map(_time, (lock.get('consumed_at'), lock.get('locked_at'), lock.get('game_time')))
        if not consumed:
            reasons.append('unconsumed_lock')
        elif not locked or consumed < locked:
            reasons.append('invalid_lock_consumption_time')
        if not (locked and game and locked < game):
            reasons.append('lock_not_pregame')
        if not lock.get('id') or not lock.get('source_artifact_path'):
            reasons.append('lock_provenance_unavailable')
    if archive:
        recovery = archive.get('archive_outcome_reconciliation_source')
        flags = str(archive.get('input_quality_flags') or '').lower()
        if recovery not in (None, '', 'archive') or 'recover' in flags or 'reconcil' in flags:
            reasons.append('history_recovered')
        if archive.get('result') not in {'win', 'loss', 'push', 'void'} or not _number(archive.get('pick_history_pnl')):
            reasons.append('closed_history_outcome_unavailable')
        if not archive.get('source_artifact_path'):
            reasons.append('archive_provenance_unavailable')
        if lock:
            if not _book(archive.get('bet_time_book')) or _book(archive.get('bet_time_book')) != _book(lock.get('locked_book')):
                reasons.append('archive_lock_book_mismatch')
            if not (all(_same_number(archive.get(a), lock.get(b)) for a, b in (
                ('bet_time_line', 'locked_k_line'), ('bet_time_odds', 'locked_odds')))
                and archive.get('display_verdict') == lock.get('locked_verdict')):
                reasons.append('archive_lock_quote_mismatch')
            if not all(_same_time(archive.get(a), lock.get(b)) for a, b in (
                ('bet_time_at', 'locked_at'), ('game_time', 'game_time'))):
                reasons.append('archive_lock_time_mismatch')
    return {
        'identity': dict(zip(('slate_date', 'normalized_pitcher', 'side'), key)),
        'linkage_status': 'excluded' if reasons else 'linked',
        'decision_input_status': 'validated' if decision else 'excluded',
        'selector_match': match, 'formal_prospective_credit': False,
        'decision_time': decision,
        'frozen_provenance': {k: frozen.get(k) for k in ('id', 'bundle_id', 'checkpoint', 'inserted_at', 'frozen_at', 'selector_fingerprint', 'source_artifact_path', 'source_artifact_sha256', 'source_artifact_byte_sha256')} if frozen else None,
        'lock_proof': copy.deepcopy(lock),
        'archive_context': copy.deepcopy(archive),
        'archive_explicit_official_provider': explicit_official_provider(archive or {}),
        'archive_selector_match': selector_matches(archive) if archive else None,
        'outcome_context': {k: archive.get(k) for k in ('actual_ks', 'result', 'pick_history_pnl', 'theoretical_pnl', 'archive_outcome_reconciliation_source')} if archive else None,
        'pregame_evidence': {'preclose': preclose, 'market_agreement_label': None, 'frozen_path_b': None},
        'evidence_gaps': sorted(gaps), 'exclusion_reasons': sorted(set(reasons)),
        'proof_validation_reasons': list(proof_errors),
    }


def build_packet(*, gate_c_rows, lock_rows, frozen_rows, start_date, end_date):
    start, end = date.fromisoformat(start_date).isoformat(), date.fromisoformat(end_date).isoformat()
    if start > end:
        raise ValueError('Start date must not follow end date')
    indices = {'gate_c': _index(gate_c_rows, start, end, tracked_only=True),
               'lock': _index(lock_rows, start, end), 'frozen': _index(frozen_rows, start, end)}
    keys = sorted(set().union(*(set(i) for i in indices.values())))
    conflicts = defaultdict(list)
    for name, index in indices.items():
        source_ids = defaultdict(set)
        for key, rows in index.items():
            for row in rows:
                source_id = row.get('dataset_key' if name == 'gate_c' else 'id')
                if source_id:
                    source_ids[source_id].add(key)
        for identities in source_ids.values():
            if len(identities) > 1:
                for key in identities:
                    conflicts[key].append(f'duplicate_{name}_source_id')
    records = [_record(key, {name: index.get(key, []) for name, index in indices.items()}, conflicts[key]) for key in keys]
    return {
        'schema': 'decision_time_linkage_v1', 'mode': 'offline_research_only',
        'start_date': start, 'end_date': end,
        'limits': ['No formal prospective credit or integration', 'Gate C universe uses tracked sides only',
                   'Hashes link recorded identifiers; served artifact bytes are not independently certified',
                   'Missing recovery flags do not certify complete historical provenance',
                   'Outcomes are preserved history values; no new grading or cost assumptions'],
        'summary': {
            'input_rows_in_window': {name: sum(map(len, index.values())) for name, index in indices.items()},
            'records': len(records), 'linked': sum(r['linkage_status'] == 'linked' for r in records),
            'validated_decision_inputs': sum(r['decision_input_status'] == 'validated' for r in records),
            'frozen_selector_matches': sum(r['selector_match'] is True for r in records),
            'linked_selector_matches': sum(r['selector_match'] is True and r['linkage_status'] == 'linked' for r in records),
            'archive_selector_matches': sum(r['archive_selector_match'] is True for r in records),
            'formal_prospective_credit': 0,
            'exclusion_counts': dict(sorted(Counter(reason for r in records for reason in r['exclusion_reasons']).items())),
        }, 'records': records,
    }


def read_rows(path, *, source):
    raw = Path(path).read_bytes()
    content = gzip.decompress(raw) if str(path).endswith('.gz') else raw
    text = content.decode('utf-8')
    def reject_constant(value):
        raise ValueError(f'Non-finite JSON constant: {value}')
    if str(path).removesuffix('.gz').endswith('.jsonl'):
        rows = [json.loads(line, parse_constant=reject_constant) for line in text.splitlines() if line.strip()]
    else:
        rows = json.loads(text, parse_constant=reject_constant)
        if isinstance(rows, dict):
            rows = rows.get('locks' if source == 'lock' and 'locks' in rows else 'rows')
    if not isinstance(rows, list):
        raise ValueError('Expected source row list or explicit rows envelope')
    return rows


def write_packet(packet, output_dir):
    dest = Path(output_dir).resolve()
    if dest.is_relative_to(ROOT) and not any(dest.is_relative_to(ROOT / allowed) for allowed in ('analytics/output', 'docs/research/evidence')):
        raise ValueError('Output inside repository must use a new research evidence/output directory')
    encoded = json.dumps(packet, indent=2, sort_keys=True, allow_nan=False) + '\n'
    dest.mkdir(parents=True, exist_ok=False)
    (dest / 'packet.json').write_text(encoded)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    for flag in ('gate-c', 'locks', 'frozen', 'start-date', 'end-date', 'output-dir'):
        parser.add_argument('--' + flag, required=True)
    args = parser.parse_args(argv)
    paths = {'gate_c': args.gate_c, 'lock': args.locks, 'frozen': args.frozen}
    rows = {name: read_rows(path, source=name) for name, path in paths.items()}
    packet = build_packet(gate_c_rows=rows['gate_c'], lock_rows=rows['lock'], frozen_rows=rows['frozen'], start_date=args.start_date, end_date=args.end_date)
    packet['source_files'] = {name: {'path': str(Path(path)), 'sha256': hashlib.sha256(Path(path).read_bytes()).hexdigest()} for name, path in paths.items()}
    write_packet(packet, args.output_dir)
    print(json.dumps(packet['summary'], sort_keys=True))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())

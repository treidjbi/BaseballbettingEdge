"""Offline forward-evidence acceptance only: no capture, writer, runner or credit.

Receipts are checked for internal consistency; local files cannot authenticate
when an external service actually persisted a receipt. No formal audit runs.
"""
from __future__ import annotations
import argparse
import base64
import binascii
from collections import Counter, defaultdict
import copy
from datetime import date, datetime
import gzip
import hashlib
import json
import math
from pathlib import Path
import re

from analytics.diagnostics import selective_lean_prospective_audit as audit
from analytics.diagnostics.decision_time_research_adapter import write_packet
from analytics.diagnostics.strong_base_decision_lab import path_b_coverage_bucket
from analytics.diagnostics.pitcher_k_outcome_dataset import _clv_type, _line_clv_delta
from market_infra import alternative_pick_preclose_v2 as market
from market_infra import alternative_pick_selector_v2 as selector
from market_infra.alternative_pick_selector import timing_bucket
from market_infra.alternative_pick_selection_state import _candidate_is_canonical
from market_infra.alternative_pick_evaluation_proof_v2 import build_evaluation_proof_v2, validate_evaluation_proof_v2
from market_infra.published_artifacts import canonical_payload_sha256
from pipeline.name_utils import normalize

ROOT = Path(__file__).resolve().parents[2]
SCHEMA = 'forward_pregame_evidence_v1'
ENVELOPE_FIELDS = frozenset({'schema','evidence_kind','identity','frozen','lock','artifact_proof',
    'market_proof','decision_time','agreement','preclose','path_b','provenance','content_sha256','manifest_sha256'})
MAX_BYTES = 64 * 1024 * 1024  # Offline file safety limit, not a provider/read setting.
PATH_FIELDS = ('batter_handedness_mode','lineup_used','lineup_count','lineup_split_source',
               'lineup_real_split_count','lineup_path_a_fallback_count')
CONTRACT = 'docs/superpowers/specs/2026-09-04-forward-pregame-evidence-contract.md'
DEPENDENCIES = (
    'analytics/diagnostics/forward_pregame_evidence_validator.py',
    'analytics/diagnostics/decision_time_research_adapter.py',
    'analytics/diagnostics/selective_lean_prospective_audit.py',
    'analytics/diagnostics/strong_base_decision_lab.py',
    'analytics/diagnostics/gate_f_preclose_clv_proxy_lab.py',
    'analytics/diagnostics/pitcher_k_outcome_dataset.py',
    'analytics/diagnostics/market_price_outcome_audit.py',
    'market_infra/alternative_pick_preclose_v2.py',
    'market_infra/alternative_pick_evaluation_proof_v2.py',
    'market_infra/alternative_pick_selector_v2.py',
    'market_infra/alternative_pick_selector.py',
    'market_infra/alternative_pick_selection_state.py',
    'market_infra/alternative_pick_selector_manifest_v1.json',
    'market_infra/alternative_pick_selector_manifest_v2.json',
    'market_infra/live_market_display.py',
    'market_infra/current_market_lines.py',
    'market_infra/provider_freshness.py',
    'market_infra/published_artifacts.py',
    'pipeline/name_utils.py',
)


class InvalidEvidence(ValueError):
    pass


def require(condition, reason):
    if not condition:
        raise InvalidEvidence(reason)


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'), ensure_ascii=False, allow_nan=False).encode()


def digest(value):
    return hashlib.sha256(canonical(value)).hexdigest()


def seal(envelope):
    """Explicit construction helper for synthetic/offline inputs; validation never mutates."""
    envelope['content_sha256'] = digest({k:v for k,v in envelope.items() if k!='content_sha256'})
    return envelope


def _pairs(items):
    result = {}
    for key,value in items:
        require(key not in result, 'duplicate_json_key')
        result[key]=value
    return result


def loads(text):
    def bad(value):
        raise InvalidEvidence('nonfinite_json')
    return json.loads(text, object_pairs_hook=_pairs, parse_constant=bad)


def stamp(value):
    try:
        parsed=datetime.fromisoformat(value.replace('Z','+00:00'))
        require(parsed.utcoffset() is not None, 'naive_timestamp')
        return parsed
    except (TypeError, AttributeError, ValueError) as exc:
        raise InvalidEvidence('invalid_timestamp') from exc


def number(value):
    return isinstance(value,(int,float)) and not isinstance(value,bool) and math.isfinite(value)


def integer(value):
    return isinstance(value,int) and not isinstance(value,bool) and value>=0


def odds(value):
    return number(value) and float(value).is_integer() and abs(value)>=100


def sha(value):
    return isinstance(value,str) and re.fullmatch('[0-9a-f]{64}',value) is not None


def book(value):
    return re.sub('[^a-z0-9]','',str(value or '').lower())


def key(identity):
    require(isinstance(identity,dict), 'invalid_identity')
    slate=date.fromisoformat(identity['slate_date']).isoformat()
    pitcher=identity['normalized_pitcher']; side=identity['side']
    require(isinstance(pitcher,str) and pitcher and normalize(pitcher).strip()==pitcher and side in {'over','under'},'invalid_identity')
    return (slate,pitcher,side)


def decode_receipt(receipt):
    require(isinstance(receipt,dict),'receipt_missing')
    require(isinstance(receipt.get('body_base64'),str) and len(receipt['body_base64'])<=MAX_BYTES*2,'receipt_size_or_shape')
    try:
        raw=base64.b64decode(receipt['body_base64'],validate=True)
    except (ValueError,binascii.Error) as exc:
        raise InvalidEvidence('receipt_encoding') from exc
    require(len(raw)<=MAX_BYTES,'receipt_size_or_shape')
    require(hashlib.sha256(raw).hexdigest()==receipt.get('byte_sha256'),'receipt_byte_hash_mismatch')
    return loads(raw)


def checked_receipt(receipt, cutoff, kind):
    require(isinstance(receipt,dict),'receipt_missing')
    require(stamp(receipt.get('acquired_at'))<=cutoff,kind+'_receipt_after_lock')
    require(stamp(receipt.get('source_event_at'))<=stamp(receipt['acquired_at']),kind+'_future_event')
    require(bool(receipt.get('receipt_id')) and bool(receipt.get('source_path')),kind+'_receipt_provenance')
    try:
        return decode_receipt(receipt)
    except InvalidEvidence as exc:
        if kind=='artifact' and str(exc)=='receipt_byte_hash_mismatch':
            raise InvalidEvidence('artifact_byte_hash_mismatch') from exc
        raise


def reference_manifest():
    """An inactive local reference, never an activation command or deployed manifest."""
    return dict(schema=SCHEMA, mode='offline_validation_only',
        contract_sha256=hashlib.sha256((ROOT/CONTRACT).read_bytes()).hexdigest(),
        selector_fingerprint=audit.EXPECTED_RULE_FINGERPRINT,
        baselines=dict(historical=copy.deepcopy(audit.LOCKED_HISTORICAL),current_provider=copy.deepcopy(audit.LOCKED_CURRENT_PROVIDER)),
        dependencies={p:hashlib.sha256((ROOT/p).read_bytes()).hexdigest() for p in DEPENDENCIES},
        stale_after_seconds=900,
        activation=dict(activated_at=None,first_unobserved_slate=None,capture_sink=None,review_ref=None,implementation_commit=None))


def manifest_reasons(manifest):
    expected=reference_manifest(); reasons=[]
    for name,reason in [('schema','schema_drift'),('mode','manifest_mode_drift'),('contract_sha256','contract_drift'),
                        ('selector_fingerprint','selector_drift'),('baselines','baseline_drift'),
                        ('dependencies','dependency_drift'),('stale_after_seconds','freshness_config_drift')]:
        if canonical(manifest.get(name))!=canonical(expected[name]): reasons.append(reason)
    if audit.RULE_FINGERPRINT!=audit.EXPECTED_RULE_FINGERPRINT: reasons.append('selector_drift')
    activation=manifest.get('activation') or {}
    try:
        when=stamp(activation.get('activated_at'))
        first=date.fromisoformat(activation.get('first_unobserved_slate',''))
        require(first>when.date() and first>=date(2026,8,15),'activation_not_forward')
        require(activation.get('capture_sink') and activation.get('review_ref') and
                re.fullmatch('[0-9a-f]{40}',activation.get('implementation_commit') or ''),'activation_review_missing')
    except (ValueError,TypeError) as exc:
        reasons.append(str(exc) if isinstance(exc,InvalidEvidence) and str(exc).startswith('activation_') else 'activation_unset')
    return sorted(set(reasons))


def _path_b(envelope,pitcher,artifact_sha):
    p=envelope['path_b']
    require(p.get('status')=='known' and all(k in p and p[k] is not None for k in PATH_FIELDS),'path_b_incomplete')
    count,real,fallback=(p[k] for k in ('lineup_count','lineup_real_split_count','lineup_path_a_fallback_count'))
    require(all(integer(v) for v in (count,real,fallback)) and real+fallback==count,'path_b_invalid_counts')
    require(type(p['lineup_used']) is bool and p['batter_handedness_mode'] in {'path_a','path_b'},'path_b_incomplete')
    require((p['lineup_used'] and count>0) or (not p['lineup_used'] and count==0),'path_b_invalid_counts')
    expected='none' if not p['lineup_used'] else 'mixed_real_split_cache' if real and fallback else 'real_split_cache' if real else 'path_a'
    require(p['lineup_split_source']==expected and (p['batter_handedness_mode']=='path_b' or real==0),'path_b_source_mismatch')
    require(p.get('source_artifact_sha256')==artifact_sha and all(p[k]==pitcher.get(k) for k in PATH_FIELDS),'path_b_artifact_mismatch')
    return path_b_coverage_bucket(p)


def _evaluation(pitcher,tracked,frozen,exact):
    # Mirror only the existing explicit tracked-quote overlay; scoring stays in
    # the pure V2 selector. This profile requires explicit display quote fields.
    side=frozen['side']; p=copy.deepcopy(pitcher)
    pick=copy.deepcopy(pitcher.get('ev_'+side) or {})
    for field in ('display_verdict','locked_verdict','actionable_verdict','current_verdict','verdict','raw_verdict',
                  'quality_actionable_verdict','quality_gate_level','edge','ev','adj_ev','raw_adj_ev','locked_adj_ev',
                  'market_anchor_selector','large_edge_skepticism_flag','win_prob','model_win_prob'):
        if tracked.get(field) is not None: pick[field]=tracked[field]
    if tracked.get('display_adj_ev') is not None: pick['locked_adj_ev']=tracked['display_adj_ev']
    pick.update(side=side,official_k_line=frozen['model_k_line'],odds=tracked['display_odds'])
    p.update(game_time=frozen['game_time'],k_line=frozen['model_k_line'])
    p['best_'+side+'_odds']=tracked['display_odds'];p['best_'+side+'_book']=tracked['display_book']
    return selector.evaluate_alternative_pick_v2(pitcher=p,pick=pick,exact_evidence=exact.market_evidence,
        slate_date=frozen['slate_date'],is_tracked=True,source_artifact_path=frozen['source_artifact_path'],
        source_payload_sha256=frozen['source_artifact_sha256'],source_artifact_byte_sha256=frozen['source_artifact_byte_sha256'],
        observed_at=frozen['locked_at'])


def _pregame(envelope,manifest):
    require(envelope.get('schema')==SCHEMA,'legacy_or_wrong_schema')
    require(set(envelope)==ENVELOPE_FIELDS,'envelope_schema_drift')
    require(envelope.get('evidence_kind') in {'synthetic','captured'},'evidence_kind_missing')
    require(envelope.get('manifest_sha256')==digest(manifest),'manifest_binding_mismatch')
    require(envelope.get('content_sha256')==digest({k:v for k,v in envelope.items() if k!='content_sha256'}),'envelope_digest_mismatch')
    ident=envelope['identity'];f=envelope['frozen'];lock=envelope['lock'];proof=f['evaluation_proof']
    require(bool(f.get('id')) and bool(lock.get('id')),'source_id_missing')
    require(key(ident)==key(f)==key(lock),'lock_identity_mismatch')
    require(_candidate_is_canonical(f) and ident.get('game_identity')==f.get('game_identity'),'candidate_identity_mismatch')
    L,G=stamp(f['locked_at']),stamp(f['game_time'])
    require(stamp(ident['game_time'])==stamp(lock['game_time'])==G and stamp(lock['locked_at'])==L
            and ident.get('lock_id')==lock.get('id'),'lock_identity_mismatch')
    require(f.get('checkpoint')=='frozen_pregame' and stamp(f['frozen_at'])==L
            and stamp(f['observed_at'])==L and L<=stamp(f['inserted_at'])<G,'freeze_not_pregame')
    pr=envelope['provenance']
    require(L<=stamp(f['inserted_at'])<=stamp(pr['completed_at'])<=stamp(pr['persisted_at'])<G
            and pr.get('capture_run_id'),'freeze_not_pregame')
    require(timing_bucket(L.isoformat(),G.isoformat())=='pre_30','not_pre_30')
    require(odds(f.get('official_odds')) and odds(lock.get('locked_odds')) and
            all(number(f.get(a)) and number(lock.get(b)) and f[a]==lock[b] for a,b in
                [('model_k_line','locked_k_line'),('official_odds','locked_odds')])
            and f.get('official_verdict')==lock.get('locked_verdict')
            and book(f.get('official_book'))==book(lock.get('locked_book')) and book(lock.get('locked_book')),'lock_quote_mismatch')
    valid,reasons=validate_evaluation_proof_v2(proof=proof,row=f)
    require(valid,'invalid_frozen_proof:'+','.join(reasons))
    require(proof['preclose']['freshness_status']=='fresh','frozen_preclose_pending')
    require(envelope['decision_time']==proof['normalized_inputs'],'decision_input_mismatch')
    n=proof['normalized_inputs']
    require(n.get('bet_timing_window')=='pre_30' and stamp(n.get('observed_at'))==L,'not_pre_30')
    require(n.get('workload_input_status')=='complete' and all(integer(n.get(k)) for k in ('last_pitch_count','days_since_last_start'))
            and all(type(n.get(k)) is bool for k in ('is_opener','starter_mismatch'))
            and n.get('opportunity_bucket') in {'normal','short_leash','deep_starter'}
            and n.get('leash_risk_bucket') in {'normal','medium','high'},'workload_incomplete')
    artifact=envelope['artifact_proof'];payload=checked_receipt(artifact,L,'artifact')
    require(lock.get('source_artifact_path')==artifact.get('source_path'),'lock_artifact_path_mismatch')
    require(artifact['byte_sha256']==lock.get('source_artifact_sha256')==f.get('lock_artifact_sha256')==f.get('source_artifact_byte_sha256'),'artifact_byte_hash_mismatch')
    require(f.get('source_artifact_sha256')==canonical_payload_sha256(payload),'artifact_logical_hash_mismatch')
    require(payload.get('date')==ident['slate_date'] and stamp(payload['generated_at'])==stamp(f['source_artifact_generated_at'])<=L,'artifact_generation_mismatch')
    pitchers=[p for p in payload['pitchers'] if normalize(p.get('pitcher','')).strip()==ident['normalized_pitcher']]
    require(len(pitchers)==1,'ambiguous_artifact_pitcher');pitcher=pitchers[0]
    require(stamp(pitcher['game_time'])==G and pitcher.get('k_line')==f['model_k_line'],'artifact_candidate_mismatch')
    picks=[p for p in pitcher['tracked_picks'] if p.get('side')==ident['side']]
    require(len(picks)==1,'ambiguous_artifact_pick');tracked=picks[0]
    require(stamp(tracked['game_time'])==G and normalize(tracked.get('pitcher','')).strip()==ident['normalized_pitcher'],
            'artifact_candidate_mismatch')
    require(all(number(tracked.get(k)) for k in ('display_k_line','display_odds')) and
            tracked['display_k_line']==f['model_k_line'] and tracked['display_odds']==f['official_odds']
            and book(tracked.get('display_book'))==book(f['official_book'])
            and tracked.get('display_verdict')==f['official_verdict'],'artifact_quote_mismatch')
    path_bucket=_path_b(envelope,pitcher,artifact['byte_sha256'])
    provider=proof['candidate']['line_source_provider']
    require(provider in {'therundown','propline'} and pitcher.get('line_source_provider')==provider,'official_provider_mismatch')
    mp=envelope['market_proof'];snapshots=[];ids=[]
    for receipt in mp['snapshots']:
        row=checked_receipt(receipt,L,'snapshot')
        require(stamp(row['observed_at'])==stamp(receipt['source_event_at']),'snapshot_event_mismatch')
        require(row.get('provider') in {'therundown','propline'} and row.get('id') and number(row.get('line'))
                and odds(row.get('american_odds')),'invalid_snapshot')
        snapshots.append(row);ids.append((row['provider'],row['id']))
    require(len(ids)==len(set(ids)),'duplicate_snapshot_delivery')
    lines=checked_receipt(mp['current_lines'],L,'current_lines')
    heartbeats=checked_receipt(mp['heartbeats'],L,'heartbeat')
    windows=checked_receipt(mp['windows'],L,'window')
    read=checked_receipt(mp['read'],L,'read')
    require(read.get('complete') is True and read.get('reason_codes')==[] and
            integer(read.get('expected_count')) and read.get('returned_count')==read['expected_count']==len(snapshots)
            and stamp(read['window_end'])==L and stamp(read['window_start'])<=stamp(windows['candidate_became_current_at'])<=L
            and all(stamp(read['window_start'])<=stamp(t)<=L for t in windows['provider_window_started_at'].values()),'market_read_incomplete')
    require(all(stamp(read['window_start'])<=stamp(s['observed_at'])<=L for s in snapshots),'snapshot_outside_read_window')
    for hb in heartbeats:
        # Builder handles provider status/freshness; receipt proves these values
        # were acquired by the decision cutoff, not by the later audit.
        require(hb.get('provider') in {'therundown','propline'},'heartbeat_provider_mismatch')
    bindings=market.resolve_candidate_bindings_v2(candidate=f,pitcher=pitcher,current_lines_by_id=lines,snapshot_rows=snapshots)
    require(bindings.get('ready') is True,'official_binding_pending')
    require(windows.get('candidate_identity')==f['candidate_identity']
            and windows.get('official_binding_key')==bindings['official_binding_key']
            and windows.get('sidecar_binding_keys')==bindings['sidecar_binding_keys'],'window_binding_mismatch')
    exact=market.build_exact_preclose_evidence_v2(candidate=f,bindings=bindings,windows=windows,snapshot_rows=snapshots,
        provider_heartbeats=heartbeats,snapshot_read_complete=read['complete'],snapshot_window_started_at=read['window_start'],
        snapshot_read_reason_codes=read['reason_codes'],observed_at=L,source_artifact_path=f['source_artifact_path'],
        source_artifact_byte_sha256=artifact['byte_sha256'],stale_after_seconds=900)
    require(exact.market_evidence.get('freshness_status')=='fresh',
            'market_pending:'+','.join(exact.evidence_window.get('reason_codes',[])))
    evaluation=_evaluation(pitcher,tracked,f,exact)
    replay=build_evaluation_proof_v2(candidate=f,evaluation=evaluation,exact_preclose=exact,
        artifact=dict(path=f['source_artifact_path'],payload=payload,payload_sha256=f['source_artifact_sha256'],
                      byte_sha256=artifact['byte_sha256'],generated_at=payload['generated_at']))
    require(replay.selection_safe and replay.proof==proof,'market_or_decision_replay_mismatch')
    toward,away=(exact.market_evidence[k] for k in ('toward_pick_count','away_from_pick_count'))
    label='market_mixed' if toward and away else 'market_with_model' if toward else 'market_against_model' if away else 'market_no_signal'
    require(envelope['agreement']==dict(status='known',label=label),'agreement_mismatch')
    require(envelope['preclose']==dict(status='known',label=proof['preclose']['label'],score=proof['preclose']['score']),'preclose_mismatch')
    return dict(selector_match=audit.selector_matches(dict(n,display_verdict=n['official_verdict'])),
                agreement=label,preclose_label=proof['preclose']['label'],path_b_bucket=path_bucket)


def _attachments(envelope,attachments):
    L,G=stamp(envelope['frozen']['locked_at']),stamp(envelope['frozen']['game_time']);lock=envelope['lock']
    grouped=defaultdict(list)
    for a in attachments:
        if a.get('envelope_sha256')==envelope['content_sha256']:
            require(a.get('identity')==envelope['identity'],'attachment_identity_mismatch')
            require(a.get('kind') in {'consumption','seed','settlement','close'},'unknown_attachment_kind')
            grouped[a['kind']].append(a)
    values={};times={}
    for kind in ('consumption','seed','settlement','close'):
        unique={digest(a):a for a in grouped[kind]}
        require(len(unique)==1,('missing_' if not unique else 'conflicting_')+kind)
        a=next(iter(unique.values()));r=a['receipt'];d=decode_receipt(r)
        require(bool(r.get('receipt_id')) and bool(r.get('source_path')),'attachment_provenance_missing')
        at=stamp(r['acquired_at']);require(stamp(r['source_event_at'])<=at,'attachment_future_event')
        require(L<=at,'attachment_before_lock')
        for field in ('slate_date','normalized_pitcher','side','game_time','locked_at','locked_k_line','locked_odds','locked_book','locked_verdict'):
            require(d.get(field)==lock.get(field),'attachment_quote_mismatch')
        values[kind]=d;times[kind]=at
    c,seed,outcome,close=(values[k] for k in ('consumption','seed','settlement','close'))
    require(c.get('lock_id')==lock['id'] and L<=stamp(c['consumed_at'])<=times['consumption']<G,'unconsumed_lock')
    require(stamp(c['consumed_at'])<=times['seed']<G and 'result' in seed and seed['result'] is None
            and _original(seed),'seed_not_original')
    require(times['settlement']>=G and _original(outcome),'settlement_not_original')
    require(outcome.get('result') in {'win','loss','push','void'} and number(outcome.get('pnl')),'settlement_unavailable')
    require(times['close']>=G and L<=stamp(close['observed_at'])<G
            and number(close.get('closing_line')) and odds(close.get('closing_odds'))
            and book(close.get('closing_book'))==book(lock['locked_book'])
            and close.get('closing_provider')==envelope['frozen']['evaluation_proof']['candidate']['line_source_provider'],
            'close_attribution_missing')
    expected_clv=_clv_type(True,lock['locked_odds']-close['closing_odds'],
                          _line_clv_delta(lock['side'],lock['locked_k_line'],close['closing_line']))
    require(close.get('clv_type')==expected_clv,'close_bucket_mismatch')
    return dict(result=outcome['result'],recorded_pnl=outcome['pnl'],final_clv=close['clv_type'],execution_costs='not_established')


def _original(row):
    return (row.get('recovery_status')=='original'
            and row.get('archive_outcome_reconciliation_source') in (None,'','archive')
            and not any(word in str(row.get('input_quality_flags') or '').lower() for word in ('recover','reconcil')))


def _frozen_rule_match(envelope):
    """Keep a known rule match visible even when another input blocks credit."""
    try:
        f=envelope['frozen'];p=f['evaluation_proof'];n=p['normalized_inputs']
        if not validate_evaluation_proof_v2(proof=p,row=f)[0]: return None
        if any(n.get(k) in (None,'','unknown') for k in
               ('official_verdict','line_bucket','model_market_relationship','quality_gate_level')): return None
        return audit.selector_matches(dict(n,display_verdict=n['official_verdict']))
    except (KeyError,TypeError,ValueError,AttributeError):
        return None


def validate_packet(packet):
    require(isinstance(packet,dict),'packet_not_object')
    if 'envelopes' not in packet:
        old=packet.get('records',packet.get('rows',[]))
        return dict(mode='offline_validation_only',formal_prospective_credit=0,manifest_reasons=['legacy_or_wrong_schema'],
                    summary=dict(legacy_rows_rejected=len(old) if isinstance(old,list) else 0),records=[])
    try:
        canonical(packet)
    except (ValueError,TypeError) as exc:
        raise InvalidEvidence('packet_not_finite_json') from exc
    manifest=packet.get('manifest') or {}
    require(isinstance(manifest,dict) and all(isinstance(packet.get(k),list) for k in
            ('envelopes','attachments','inventory')),'packet_schema_invalid')
    mreasons=manifest_reasons(manifest)
    start,end=date.fromisoformat(packet['start_date']),date.fromisoformat(packet['end_date'])
    require(start<=end,'invalid_date_bounds')
    envs=defaultdict(list);inventory=defaultdict(list);by_source=defaultdict(set)
    for e in packet['envelopes']:
        k=key(e['identity']);require(start<=date.fromisoformat(k[0])<=end,'out_of_window_identity');envs[k].append(e)
        for source in ('frozen','lock'):
            if e.get(source,{}).get('id'): by_source[(source,e[source]['id'])].add(k)
    for entry in packet.get('inventory',[]):
        k=key(entry['identity']);require(start<=date.fromisoformat(k[0])<=end,'out_of_window_inventory');inventory[k].append(entry)
    cross={k for ks in by_source.values() if len(ks)>1 for k in ks}
    records=[]
    for k in sorted(set(envs)|set(inventory)):
        reasons=[];pregame=False;match=None;metadata={};lifecycle={}
        candidates={digest(e):e for e in envs[k]}
        e=next(iter(candidates.values())) if len(candidates)==1 else None
        if not candidates: reasons.append('missing_capture')
        elif len(candidates)>1: reasons.append('conflicting_retry')
        if k in cross: reasons.append('reused_source_id')
        if len(inventory[k])!=1: reasons.append('missing_or_duplicate_inventory')
        elif e and (inventory[k][0].get('identity')!=e['identity'] or inventory[k][0].get('status')!='captured'):
            reasons.append('inventory_mismatch')
        if e and not reasons:
            match=_frozen_rule_match(e)
            try:
                metadata=_pregame(e,manifest);pregame=True;match=metadata['selector_match']
            except (InvalidEvidence,KeyError,TypeError,ValueError,AttributeError) as exc:
                reasons.append(str(exc) if isinstance(exc,InvalidEvidence) else 'malformed_envelope')
            try:
                lifecycle=_attachments(e,packet.get('attachments',[]))
                if lifecycle['result'] not in {'win','loss'}:
                    reasons.append('settlement_not_win_loss')
            except (InvalidEvidence,KeyError,TypeError,ValueError,AttributeError) as exc:
                reasons.append(str(exc) if isinstance(exc,InvalidEvidence) else 'malformed_attachment')
        activation_ok=not mreasons
        if e and activation_ok:
            a=manifest['activation']
            if k[0]<a['first_unobserved_slate'] or stamp(e['frozen']['locked_at'])<stamp(a['activated_at']):
                reasons.append('before_activation');activation_ok=False
        records.append(dict(identity=dict(zip(('slate_date','normalized_pitcher','side'),k)),pregame_valid=pregame,
            selector_match=match,decision_digest=e.get('content_sha256') if e else None,
            eligible_input_candidate=bool(pregame and match and not reasons and activation_ok),
            formal_prospective_credit=False,reasons=sorted(set(reasons)),**{k:v for k,v in metadata.items() if k!='selector_match'},
            outcome_context=lifecycle))
        records[-1]['capture_context']=copy.deepcopy(inventory[k])
        records[-1]['frozen_proof_reasons']=copy.deepcopy(e.get('frozen',{}).get('evaluation_proof',{}).get('decision',{}).get('reason_codes',[])) if e else []
    known_digests={e.get('content_sha256') for group in envs.values() for e in group}
    orphans=sum(a.get('envelope_sha256') not in known_digests for a in packet.get('attachments',[]))
    if orphans:
        mreasons.append('orphan_attachment')
        for r in records: r['eligible_input_candidate']=False
    return dict(schema=SCHEMA,mode='offline_validation_only',formal_prospective_credit=0,
        limits=['Internal receipt consistency only; persistence times are not externally authenticated',
                'Synthetic activation declarations never activate capture or an audit',
                'Eligible inputs do not establish baseline reconciliation, diversity, profitability or promotion'],
        manifest_reasons=sorted(set(mreasons)),summary=dict(records=len(records),
            pregame_valid=sum(r['pregame_valid'] for r in records),eligible_input_candidates=sum(r['eligible_input_candidate'] for r in records),
            missing_capture=sum('missing_capture' in r['reasons'] for r in records),orphan_attachments=orphans,
            exclusions=dict(sorted(Counter(x for r in records for x in r['reasons']).items()))),records=records)


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--input',required=True);parser.add_argument('--output-dir',required=True)
    args=parser.parse_args(argv);path=Path(args.input)
    opener=gzip.open if str(path).endswith('.gz') else open
    with opener(path,'rb') as stream: body=stream.read(MAX_BYTES+1)
    require(len(body)<=MAX_BYTES,'input_too_large')
    output=validate_packet(loads(body))
    output['input_sha256']=hashlib.sha256(body).hexdigest()
    write_packet(output,args.output_dir)
    print(json.dumps(output['summary'],sort_keys=True))
    return 0


if __name__=='__main__':
    raise SystemExit(main())

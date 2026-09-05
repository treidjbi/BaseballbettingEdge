"""Bounded offline source-to-envelope feasibility. No network, writers or credit.

Source timestamps are preserved assertions, never replaced by this run's clock.
Local internal consistency cannot authenticate acquisition or original seeding.
"""
from __future__ import annotations

import argparse
from collections import Counter, defaultdict
import copy
from datetime import date
import gzip
import hashlib
import json
import os
from pathlib import Path
from time import perf_counter

from analytics.diagnostics import forward_pregame_evidence_validator as v

ROOT = Path(__file__).resolve().parents[2]
SCHEMA = 'forward_capture_sources_v1'
MAX_INPUT_BYTES = 64 * 1024 * 1024
MAX_OUTPUT_BYTES = 64 * 1024 * 1024
MAX_ENVELOPE_BYTES = 4 * 1024 * 1024
MAX_CANDIDATES = 32
CAPTURE_FIELDS = ('artifact_proof','market_proof','decision_time','agreement','preclose','path_b','provenance')
QUOTE_FIELDS = ('slate_date','normalized_pitcher','side','game_time','locked_at',
                'locked_k_line','locked_odds','locked_book','locked_verdict')


def _reason(exc, fallback):
    return str(exc) if isinstance(exc, v.InvalidEvidence) else fallback


def _key(row, slate):
    key = v.key(row)
    v.require(key[0] == slate, 'multiple_slates')
    v.require(len(key[1]) <= 128, 'invalid_pitcher_length')
    return key


def _read_check(capture):
    receipt = capture['market_proof']['read']
    read = v.decode_receipt(receipt)
    pages = read.get('page_row_counts')
    v.require(read.get('provider_run_read_complete') is True, 'provider_run_read_incomplete')
    v.require(read.get('page_size') == 1000 and isinstance(pages,list) and 1 <= len(pages) <= 5
              and all(type(n) is int and 0 <= n <= 1000 for n in pages), 'snapshot_page_audit_invalid')
    v.require(not (len(pages)==5 and pages[-1]==1000), 'snapshot_page_cap_reached')
    v.require(pages[-1] < 1000 and all(n==1000 for n in pages[:-1]), 'snapshot_read_not_exhausted')
    v.require(sum(pages)==read.get('returned_count')==len(capture['market_proof']['snapshots']), 'snapshot_page_count_mismatch')


def _seed_check(envelope, attachments):
    """Check pregame lifecycle only; outcomes cannot be prerequisites for capture."""
    lock = envelope['lock']; identity = envelope['identity']
    L, G = v.stamp(lock['locked_at']), v.stamp(lock['game_time'])
    values = {}; times = {}
    for kind in ('consumption','seed'):
        matches = {v.digest(a):a for a in attachments if a.get('kind')==kind and a.get('identity')==identity}
        v.require(len(matches)==1, ('missing_' if not matches else 'conflicting_')+kind)
        receipt = next(iter(matches.values()))['receipt']; body = v.decode_receipt(receipt)
        at = v.stamp(receipt['acquired_at'])
        v.require(bool(receipt.get('receipt_id')) and bool(receipt.get('source_path')), 'attachment_provenance_missing')
        v.require(v.stamp(receipt['source_event_at']) <= at and L <= at < G, 'seed_or_consumption_not_pregame')
        v.require(all(body.get(k)==lock.get(k) for k in QUOTE_FIELDS), 'attachment_quote_mismatch')
        values[kind], times[kind] = body, at
    c, seed = values['consumption'], values['seed']
    v.require(c.get('lock_id')==lock['id'] and L <= v.stamp(c['consumed_at']) <= times['consumption'], 'unconsumed_lock')
    v.require(v.stamp(c['consumed_at']) <= times['seed'] and 'result' in seed and seed['result'] is None
              and v._original(seed), 'seed_not_original')
    seed_receipt=next(a['receipt'] for a in attachments if a.get('kind')=='seed' and a.get('identity')==identity)
    v.require(v.stamp(c['consumed_at']) <= v.stamp(seed_receipt['source_event_at']), 'seed_witness_before_consumption')
    v.require(isinstance(seed.get('source_run_id'),str) and 0 < len(seed['source_run_id']) <= 128
              and seed.get('source_event_type')=='ordinary_ungraded_lock_witness', 'seed_run_provenance_missing')


def assess(bundle):
    """Return deterministic diagnostics and a newly assembled offline packet."""
    v.require(isinstance(bundle,dict) and bundle.get('schema')==SCHEMA, 'source_schema_invalid')
    v.require(set(bundle)=={'schema','slate_date','evidence_kind','manifest','source_scope',
                           'frozen_rows','lock_rows','captures','attachments'}, 'source_schema_drift')
    v.require(len(v.canonical(bundle)) <= MAX_INPUT_BYTES, 'input_cap_exceeded')
    slate = date.fromisoformat(bundle['slate_date']).isoformat()
    v.require(bundle.get('evidence_kind') in {'synthetic','historical','captured_unverified'}, 'source_kind_invalid')
    v.require(all(isinstance(bundle.get(k),list) for k in ('frozen_rows','lock_rows','captures','attachments')), 'source_lists_invalid')
    manifest = bundle.get('manifest')
    v.require(isinstance(manifest,dict), 'manifest_missing')
    attempt = [r for r in v.manifest_reasons(manifest) if r!='activation_unset']
    if manifest.get('activation') != v.reference_manifest()['activation']:
        attempt.append('activation_must_be_unset')
    scope = bundle.get('source_scope') or {}
    if (scope.get('complete') is not True or type(scope.get('frozen_count')) is not int
            or type(scope.get('lock_count')) is not int or scope['frozen_count'] != len(bundle['frozen_rows'])
            or scope['lock_count'] != len(bundle['lock_rows'])):
        attempt.append('source_scope_incomplete')
    groups = {kind:defaultdict(list) for kind in ('frozen','lock','capture')}
    ids = {kind:defaultdict(list) for kind in ('frozen','lock')}
    for kind, source in [('frozen','frozen_rows'),('lock','lock_rows'),('capture','captures')]:
        for row in bundle[source]:
            key = _key(row['identity'] if kind=='capture' else row, slate)
            groups[kind][key].append(row)
            if kind!='capture': ids[kind][row.get('id')].append(row)
    keys = set().union(*(set(g) for g in groups.values()))
    if len(keys)>MAX_CANDIDATES: attempt.append('candidate_cap_exceeded')
    if not keys: attempt.append('empty_opportunity_inventory')
    packet = dict(manifest=copy.deepcopy(manifest), start_date=slate,end_date=slate,
                  envelopes=[], attachments=[], inventory=[])
    records = []
    for key in sorted(keys):
        row = dict(identity=dict(zip(('slate_date','normalized_pitcher','side'),key)),
                   pregame_internal_valid=False, seed_internal_valid=False, selector_match=None,
                   internally_complete=False, reasons=[], source_sha256={}, envelope_bytes=0)
        sources = {}
        for kind in ('frozen','lock'):
            found = groups[kind][key]
            if not found: row['reasons'].append('missing_'+kind)
            elif len(found)!=1 or not found[0].get('id') or len(ids[kind][found[0]['id']])!=1:
                row['reasons'].append('ambiguous_'+kind+'_id')
            else:
                sources[kind]=found[0];row['source_sha256'][kind]=v.digest(found[0])
        captures = {v.digest(c):c for c in groups['capture'][key]}
        if not captures: row['reasons'].append('missing_capture')
        elif len(captures)!=1: row['reasons'].append('conflicting_capture')
        else:
            c = next(iter(captures.values()));row['source_sha256']['capture']=v.digest(c)
            if len(sources)==2 and not attempt:
                try:
                    v.require(set(c)==set(CAPTURE_FIELDS)|{'identity','frozen_id','lock_id'}, 'capture_source_schema_drift')
                    v.require(c.get('frozen_id')==sources['frozen']['id'] and c.get('lock_id')==sources['lock']['id'], 'source_reference_mismatch')
                    envelope = {k:copy.deepcopy(c[k]) for k in CAPTURE_FIELDS}
                    envelope.update(schema=v.SCHEMA, evidence_kind='synthetic' if bundle['evidence_kind']=='synthetic' else 'captured',
                        identity=copy.deepcopy(c['identity']), frozen=copy.deepcopy(sources['frozen']), lock=copy.deepcopy(sources['lock']),
                        manifest_sha256=v.digest(manifest))
                    v.seal(envelope)
                    row['envelope_bytes'] = len(v.canonical(envelope))
                    if row['envelope_bytes']>MAX_ENVELOPE_BYTES:
                        attempt.append('envelope_cap_exceeded')
                        row['reasons'].append('envelope_cap_exceeded')
                    else:
                        row['selector_match'] = v._frozen_rule_match(envelope)
                        packet['envelopes'].append(envelope)
                        try:
                            _read_check(c)
                            details = v._pregame(envelope,manifest)
                            row['pregame_internal_valid']=True
                            row['selector_match']=details['selector_match']
                        except (ValueError,KeyError,TypeError,AttributeError) as exc:
                            row['reasons'].append(_reason(exc,'malformed_pregame_sources'))
                        try:
                            _seed_check(envelope,bundle['attachments']);row['seed_internal_valid']=True
                        except (ValueError,KeyError,TypeError,AttributeError) as exc:
                            row['reasons'].append(_reason(exc,'malformed_seed_sources'))
                        for a in bundle['attachments']:
                            if a.get('identity')==envelope['identity']:
                                packet['attachments'].append(dict(copy.deepcopy(a),envelope_sha256=envelope['content_sha256']))
                except (ValueError,KeyError,TypeError,AttributeError) as exc:
                    row['reasons'].append(_reason(exc,'malformed_capture_sources'))
        if 'frozen' in sources:
            f=sources['frozen']
            try:
                if f['evaluation_proof']['preclose']['freshness_status']=='pending':row['reasons'].append('frozen_preclose_pending')
                if row['selector_match'] is None:row['selector_match']=v._frozen_rule_match(dict(frozen=f))
            except (KeyError,TypeError):row['reasons'].append('missing_frozen_proof')
        for kind in ('consumption','seed'):
            if not any(a.get('kind')==kind and _key(a['identity'],slate)==key for a in bundle['attachments']):
                row['reasons'].append('missing_'+kind)
        records.append(row)
    captured_identities={v.digest(c['identity']) for c in bundle['captures']}
    for a in bundle['attachments']:
        if set(a)!={'kind','identity','receipt'} or a.get('kind') not in {'consumption','seed','settlement','close'}:
            attempt.append('attachment_schema_drift')
        if _key(a['identity'],slate) not in keys: attempt.append('orphan_attachment')
        elif bundle['captures'] and v.digest(a['identity']) not in captured_identities:attempt.append('attachment_identity_mismatch')
    if attempt:
        packet['envelopes']=[];packet['attachments']=[]
    envelope_by_key = {v.key(e['identity']):e for e in packet['envelopes']}
    for row in records:
        row['reasons']=sorted(set(row['reasons'] + (['attempt_incomplete'] if attempt else [])))
        row['internally_complete']=bool(row['pregame_internal_valid'] and row['seed_internal_valid'] and not row['reasons'])
        e=envelope_by_key.get(v.key(row['identity']))
        packet['inventory'].append(dict(identity=copy.deepcopy(e['identity'] if e else row['identity']),
            status='captured' if e else 'failed', reasons=row['reasons']))
    report = dict(schema='forward_capture_feasibility_v1', evidence_kind=bundle['evidence_kind'], slate_date=slate,
        decision='no_live_feasibility_established', trusted_live_feasible=False, formal_prospective_credit=0,
        limits=dict(candidates=MAX_CANDIDATES,envelope_bytes=MAX_ENVELOPE_BYTES,input_bytes=MAX_INPUT_BYTES,
                    output_bytes=MAX_OUTPUT_BYTES,snapshot_pages=5,page_size=1000),
        source_scope=copy.deepcopy(scope), source_bundle_sha256=v.digest(bundle),
        attempt_reasons=sorted(set(attempt)), records=records,
        caveat='Local assertions only; source inventory, acquisition times and ordinary seed provenance are not externally authenticated')
    _summarize(report)
    return report,packet


def _summarize(report):
    records=report['records']
    report['summary']=dict(opportunities=len(records),known_rule_matches=sum(r['selector_match'] is True for r in records),
        pregame_internal_valid=sum(r['pregame_internal_valid'] for r in records),
        seed_internal_valid=sum(r['seed_internal_valid'] for r in records),
        internally_complete_inputs=sum(r['internally_complete'] for r in records),
        exclusions=dict(sorted(Counter(x for r in records for x in r['reasons']).items())))


def _atomic_file(dest,name,body):
    temporary=dest/(name+'.tmp')
    with temporary.open('xb') as stream:
        stream.write(body);stream.flush();os.fsync(stream.fileno())
    os.replace(temporary,dest/name)
    descriptor=os.open(dest,os.O_RDONLY)
    try:os.fsync(descriptor)
    finally:os.close(descriptor)


def run_file(source,output_dir):
    source=Path(source);dest=Path(output_dir).resolve()
    allowed=ROOT/'analytics/output/forward_capture_feasibility'
    if dest.is_relative_to(ROOT) and (not dest.is_relative_to(allowed) or dest==allowed):
        raise ValueError('Use a new research output directory under analytics/output/forward_capture_feasibility')
    if dest.exists():raise FileExistsError(dest)
    started=perf_counter()
    opener=gzip.open if source.suffix=='.gz' else open
    with opener(source,'rb') as stream:raw=stream.read(MAX_INPUT_BYTES+1)
    v.require(len(raw)<=MAX_INPUT_BYTES,'input_cap_exceeded')
    bundle=v.loads(raw);report,packet=assess(bundle)
    report['local_measurements']=dict(input_uncompressed_bytes=len(raw),parse_and_validation_seconds=perf_counter()-started,
        input_file=str(source.resolve()),input_uncompressed_sha256=hashlib.sha256(raw).hexdigest())
    bodies={'report.json':v.canonical(report),'packet.json':v.canonical(packet)}
    if sum(map(len,bodies.values()))+4096>MAX_OUTPUT_BYTES:
        report['attempt_reasons']=sorted(set(report['attempt_reasons']+['output_cap_exceeded']))
        for r in report['records']:
            r['internally_complete']=False;r['reasons']=sorted(set(r['reasons']+['attempt_incomplete']))
        _summarize(report);bodies={'report.json':v.canonical(report)}
    marker=v.canonical(dict(complete=True,formal_prospective_credit=0,
        files={name:dict(bytes=len(body),sha256=hashlib.sha256(body).hexdigest()) for name,body in bodies.items()}))
    v.require(sum(map(len,bodies.values()))+len(marker)<=MAX_OUTPUT_BYTES,'output_cap_prevents_complete_inventory')
    dest.mkdir(parents=True,exist_ok=False)
    for name,body in bodies.items():_atomic_file(dest,name,body)
    _atomic_file(dest,'COMPLETED.json',marker)
    return report


def read_completed(directory):
    dest=Path(directory);marker=v.loads((dest/'COMPLETED.json').read_bytes())
    if marker.get('complete') is not True or set(marker.get('files',{})) not in ({'report.json'},{'report.json','packet.json'}):
        raise ValueError('Invalid completion manifest')
    if {p.name for p in dest.iterdir()} != set(marker['files'])|{'COMPLETED.json'}:raise ValueError('Incomplete output files')
    for name,info in marker['files'].items():
        body=(dest/name).read_bytes()
        if len(body)!=info['bytes'] or hashlib.sha256(body).hexdigest()!=info['sha256']:raise ValueError('Output digest mismatch')
    return marker


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--input',required=True);parser.add_argument('--output-dir',required=True)
    args=parser.parse_args(argv)
    report=run_file(args.input,args.output_dir)
    print(json.dumps(dict(decision=report['decision'],summary=report['summary'],attempt_reasons=report['attempt_reasons']),sort_keys=True))
    return 0


if __name__=='__main__':raise SystemExit(main())

"""Generate once, or verify, a synthetic offline acceptance packet. No network."""
from __future__ import annotations
import argparse
import copy
import gzip
import hashlib
import json
from pathlib import Path
import runpy
import sys

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[3]
sys.path.insert(0,str(ROOT))
from analytics.diagnostics import forward_pregame_evidence_validator as v


def sha(path): return hashlib.sha256(path.read_bytes()).hexdigest()


def build_inputs():
    factory=runpy.run_path(str(ROOT/'tests/forward_evidence_factory.py'))
    build=factory['build_case'];receipt=factory['receipt'];date=factory['DATE'];lock=factory['LOCK']
    cases={
        'toward_path_b_fallback':build(), 'against_path_a':build('against','path_a'),
        'mixed_market':build('mixed'), 'neutral_market':build('neutral'),
        'under_real_splits':build(side='under',coverage='real'),
        'mixed_splits':build(coverage='mixed'), 'known_no_lineup':build(coverage='none'),
        'inactive':build(activated=False), 'timing_at_15':build(minutes=15),
        'timing_after_30':build(minutes=30.0001),
        'negative_proxy_existing_v2_limit':build(edge=.21,probability=.65,adjusted_ev=.4,allow_pending=True),
    }
    def reseal(p):
        e=p['envelopes'][0];v.seal(e)
        for a in p['attachments']: a['envelope_sha256']=e['content_sha256']
    p=build();p['envelopes'][0]['market_proof']['snapshots'][0]['acquired_at']=date+'T20:11:00+00:00';reseal(p);cases['late_snapshot_receipt']=p
    p=build();e=p['envelopes'][0];d=v.decode_receipt(e['market_proof']['read']);d.update(complete=False,reason_codes=['snapshot_page_cap_reached']);e['market_proof']['read']=receipt(d,lock);reseal(p);cases['page_cap']=p
    p=build();p['envelopes'][0]['lock']['locked_book']='draftkings';reseal(p);cases['book_conflict']=p
    p=build();p['envelopes'][0]['path_b'].pop('batter_handedness_mode');reseal(p);cases['missing_path_b']=p
    p=build();p['attachments']=[a for a in p['attachments'] if a['kind']!='consumption'];cases['unconsumed']=p
    p=build();a=next(a for a in p['attachments'] if a['kind']=='seed');d=v.decode_receipt(a['receipt']);d['recovery_status']='unknown';a['receipt']=receipt(d,date+'T20:12:00+00:00');cases['unknown_seed']=p
    p=build();p['envelopes'].append(copy.deepcopy(p['envelopes'][0]));cases['identical_retry']=p
    p=copy.deepcopy(p);p['envelopes'][1]['provenance']['capture_run_id']='conflict';v.seal(p['envelopes'][1]);cases['conflicting_retry']=p
    p=build();p['envelopes']=[];p['inventory'][0].update(status='failed',reasons=['capture_failed']);cases['missing_capture']=p
    # Complete-input score probe: does not alter any production helper.
    original=build.__globals__['build_evaluation_proof_v2'];probe={}
    from market_infra.alternative_pick_selector_v2 import preclose_proxy_score_v2
    def capture(**kwargs):
        probe.update(preclose_proxy_score_v2(dict(kwargs['exact_preclose'].market_evidence,**kwargs['evaluation'].normalized_inputs),canonical_adjusted_ev=kwargs['evaluation'].normalized_inputs['adjusted_ev']))
        return original(**kwargs)
    build.__globals__['build_evaluation_proof_v2']=capture
    try: build(edge=.21,probability=.65,adjusted_ev=.4,allow_pending=True)
    finally: build.__globals__['build_evaluation_proof_v2']=original
    return cases,probe


def check(cases,probe):
    reports={name:v.validate_packet(packet) for name,packet in cases.items()}
    positives={'toward_path_b_fallback','against_path_a','mixed_market','neutral_market','under_real_splits','mixed_splits','known_no_lineup','identical_retry'}
    for name,report in reports.items():
        assert report['formal_prospective_credit']==0,name
        assert report['summary']['eligible_input_candidates']==int(name in positives),(name,report)
    legacy_path=ROOT/'docs/research/evidence/2026-09-04-decision-time-adapter/run/packet.json.gz'
    frozen_path=ROOT/'docs/research/evidence/2026-09-04-decision-time-adapter/frozen-source.json.gz'
    legacy=v.validate_packet(json.loads(gzip.decompress(legacy_path.read_bytes())))
    old_frozen=json.loads(gzip.decompress(frozen_path.read_bytes()))
    frozen=v.validate_packet({'records':old_frozen['rows']})
    assert legacy['summary']['legacy_rows_rejected']==352
    assert frozen['summary']['legacy_rows_rejected']==327
    assert legacy['formal_prospective_credit']==frozen['formal_prospective_credit']==0
    assert probe['score']<0 and probe['label']=='weak_preclose_clv_proxy'
    previous=runpy.run_path(str(legacy_path.parent.parent/'reproduce.py'))['verify']()
    return dict(mode='synthetic_acceptance_only',case_count=len(cases),accepted_input_cases=len(positives),
        formal_prospective_credit=0,real_capture_active=False,
        case_reports=reports,negative_score_probe=probe,legacy_adapter=legacy,legacy_frozen=frozen,
        unchanged_adapter_summary=previous['summary'],source_hashes={
            str(legacy_path.relative_to(ROOT)):sha(legacy_path),str(frozen_path.relative_to(ROOT)):sha(frozen_path)},
        validator_sha256=sha(ROOT/'analytics/diagnostics/forward_pregame_evidence_validator.py'),
        factory_sha256=sha(ROOT/'tests/forward_evidence_factory.py'))


def verify():
    cases=json.loads(gzip.decompress((HERE/'run/synthetic-inputs.json.gz').read_bytes()))
    saved=json.loads((HERE/'run/acceptance.json').read_text())
    result=check(cases,saved['negative_score_probe'])
    assert result==saved,'Saved acceptance no longer matches current validator/sources'
    # Regenerate the synthetic inputs as well: do not only trust saved labels.
    regenerated,probe=build_inputs()
    assert regenerated==cases and probe==saved['negative_score_probe']
    return result


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--create',action='store_true');args=parser.parse_args()
    if args.create:
        cases,probe=build_inputs();report=check(cases,probe)
        dest=HERE/'run';dest.mkdir(exist_ok=False)
        (dest/'synthetic-inputs.json.gz').write_bytes(gzip.compress(v.canonical(cases),mtime=0))
        (dest/'acceptance.json').write_text(json.dumps(report,indent=2,sort_keys=True)+'\n')
        (dest/'inactive-reference-manifest.json').write_text(json.dumps(v.reference_manifest(),indent=2,sort_keys=True)+'\n')
    else: report=verify()
    print(json.dumps({k:report[k] for k in ('mode','case_count','accepted_input_cases','formal_prospective_credit','real_capture_active','negative_score_probe')},indent=2))

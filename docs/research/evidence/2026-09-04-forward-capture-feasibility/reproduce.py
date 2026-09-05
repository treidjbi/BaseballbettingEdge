"""Offline feasibility acceptance: synthetic witnesses and one preserved slate."""
from __future__ import annotations
import argparse
import copy
import gzip
import hashlib
import json
from pathlib import Path
import runpy
import subprocess
import sys
import tempfile

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[3]
sys.path.insert(0,str(ROOT))
from analytics.diagnostics import forward_capture_feasibility as m
from analytics.diagnostics import forward_pregame_evidence_validator as v


def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()


def inputs():
    f=runpy.run_path(str(ROOT/'tests/forward_capture_factory.py'));build=f['source_bundle'];receipt=f['factory']['receipt'];lock=f['factory']['LOCK']
    cases={
        'strong_fallback':build(), 'weak_negative':build(edge=.21,probability=.65,adjusted_ev=.4),
        'neutral':build(agreement='neutral'),'against':build(agreement='against'),
        'known_no_lineup':build(coverage='none'),'mixed_market':build(agreement='mixed'),
    }
    b=build();b['attachments']=[a for a in b['attachments'] if a['kind']!='seed'];cases['missing_seed']=b
    b=build();a=next(a for a in b['attachments'] if a['kind']=='seed');body=v.decode_receipt(a['receipt']);body['recovery_status']='recovered';a['receipt']=receipt(body,'2026-09-06T20:12:00+00:00',name='seed');cases['recovered_seed']=b
    b=build();b['captures'][0]['market_proof']['snapshots'][0]['acquired_at']='2026-09-06T20:11:00+00:00';cases['late_receipt_early_event']=b
    b=build();read=b['captures'][0]['market_proof']['read'];body=v.decode_receipt(read);body.update(page_row_counts=[1000]*5);b['captures'][0]['market_proof']['read']=receipt(body,lock,name='read');cases['full_last_page']=b
    b=build();c=b['captures'][0];snap=c['market_proof']['snapshots'][0];body=v.decode_receipt(snap);body['american_odds']=128;c['market_proof']['snapshots'][0]=receipt(body,snap['acquired_at'],event_at=snap['source_event_at'],name='changed-snapshot');cases['exact_replay_mismatch']=b
    b=build();b['captures']*=2;cases['identical_retry']=b
    b=copy.deepcopy(b);b['captures'][1]=copy.deepcopy(b['captures'][1]);b['captures'][1]['provenance']['capture_run_id']='conflict';cases['conflicting_retry']=b
    b=build();b['captures']=[];cases['missing_capture']=b
    b=build();b['captures'][0]['provenance']['oversize_witness']='z'*(4*1024*1024);cases['envelope_byte_cap']=b
    b=build()
    for i in range(32):
        extra=copy.deepcopy(b['lock_rows'][0]);extra.update(id=f'additional-{i}',normalized_pitcher=f'synthetic pitcher {i}');b['lock_rows'].append(extra)
    b['source_scope']['lock_count']=33;cases['candidate_33_cap']=b
    frozen_path=ROOT/'docs/research/evidence/2026-09-04-decision-time-adapter/frozen-source.json.gz'
    lock_path=ROOT/'docs/research/evidence/2026-09-04-research-lineage/compact-and-lock-source.json.gz'
    frozen_source=json.loads(gzip.decompress(frozen_path.read_bytes()));lock_source=json.loads(gzip.decompress(lock_path.read_bytes()))
    slate='2026-09-03'
    frozen=[r for r in frozen_source['rows'] if r['slate_date']==slate]
    locks=[r for r in lock_source['locks'] if r['slate_date']==slate]
    cases['historical_september_3']=dict(schema=m.SCHEMA,slate_date=slate,evidence_kind='historical',
        manifest=v.reference_manifest(),source_scope=dict(complete=True,frozen_count=len(frozen),lock_count=len(locks)),
        frozen_rows=frozen,lock_rows=locks,captures=[],attachments=[])
    source_info=dict(slate=slate,frozen_export_captured_at=frozen_source['captured_at'],lock_export_captured_at=lock_source['captured_at'],
        lock_rows_with_recorded_consumed_at=sum(bool(r.get('consumed_at')) for r in locks),
        original_file_sha256={str(p.relative_to(ROOT)):sha(p) for p in (frozen_path,lock_path)},
        interpretation='Exact one-slate filtering of complete preserved exports; no receipt or timestamp inferred')
    return cases,source_info


def run(cases):
    reports={};packets={};measurements={}
    accepted={'strong_fallback','weak_negative','neutral','against','known_no_lineup','mixed_market','identical_retry'}
    with tempfile.TemporaryDirectory(prefix='bbe-forward-capture-') as temp:
        root=Path(temp)
        for name,bundle in cases.items():
            source=root/(name+'.json.gz');source.write_bytes(gzip.compress(v.canonical(bundle),mtime=0))
            destination=root/name
            measured=m.run_file(source,destination);marker=m.read_completed(destination)
            deterministic,packet=m.assess(bundle)
            assert {k:x for k,x in measured.items() if k!='local_measurements'}==deterministic
            assert deterministic['formal_prospective_credit']==0 and not deterministic['trusted_live_feasible']
            assert deterministic['summary']['internally_complete_inputs']==int(name in accepted),(name,deterministic)
            assert all(x is None for x in packet['manifest']['activation'].values())
            measurements[name]=dict(**{k:x for k,x in measured['local_measurements'].items() if k!='input_file'},
                output_files_bytes=sum(r['bytes'] for r in marker['files'].values())+(destination/'COMPLETED.json').stat().st_size,
                completion_files=list(marker['files']))
            reports[name]=deterministic;packets[name]=packet
    historical=reports['historical_september_3']
    assert historical['summary']['opportunities']==12
    assert historical['summary']['internally_complete_inputs']==0
    assert historical['summary']['exclusions']['frozen_preclose_pending']==12
    assert historical['summary']['exclusions']['missing_seed']==12
    assert len(reports['candidate_33_cap']['records'])==33
    previous=runpy.run_path(str(ROOT/'docs/research/evidence/2026-09-04-signed-score-implementation/reproduce.py'))['run']()[1]
    prior_files=subprocess.run(['git','ls-tree','-r','--name-only','980ebb30','--','docs/research/evidence/2026-09-04-signed-score-implementation'],cwd=ROOT,text=True,capture_output=True,check=True).stdout.splitlines()
    prior_hashes={}
    for path in prior_files:
        before=subprocess.run(['git','show','980ebb30:'+path],cwd=ROOT,capture_output=True,check=True).stdout
        assert before==(ROOT/path).read_bytes(),path
        prior_hashes[path]=sha(ROOT/path)
    report=dict(mode='offline_feasibility_acceptance',case_count=len(cases),synthetic_cases=len(cases)-1,
        internally_complete_synthetic_cases=len(accepted),trusted_live_feasible=False,formal_prospective_credit=0,
        implementation_sha256={str(p.relative_to(ROOT)):sha(p) for p in (
            ROOT/'analytics/diagnostics/forward_capture_feasibility.py',ROOT/'tests/forward_capture_factory.py')},
        case_reports=reports,previous_acceptance=dict(case_count=previous['case_count'],accepted=previous['accepted_synthetic_input_cases'],credit=previous['formal_prospective_credit']),
        old_evidence_files_verified=len(previous['preserved_file_sha256'])+len(prior_hashes),
        prior_implementation_file_sha256=prior_hashes)
    return report,packets,measurements


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--create',action='store_true');args=parser.parse_args()
    cases,source_info=inputs();report,packets,measurements=run(cases);report['historical_source']=source_info
    if args.create:
        dest=HERE/'run';dest.mkdir(exist_ok=False)
        (dest/'source-bundles.json.gz').write_bytes(gzip.compress(v.canonical(cases),mtime=0))
        (dest/'assembled-packets.json.gz').write_bytes(gzip.compress(v.canonical(packets),mtime=0))
        (dest/'acceptance.json').write_text(json.dumps(report,indent=2,sort_keys=True)+'\n')
        (dest/'measurements.json').write_text(json.dumps(measurements,indent=2,sort_keys=True)+'\n')
    else:
        assert cases==json.loads(gzip.decompress((HERE/'run/source-bundles.json.gz').read_bytes()))
        assert packets==json.loads(gzip.decompress((HERE/'run/assembled-packets.json.gz').read_bytes()))
        assert report==json.loads((HERE/'run/acceptance.json').read_text())
        saved=json.loads((HERE/'run/measurements.json').read_text())
        assert set(saved)==set(measurements)
        assert all(r['output_files_bytes']<=m.MAX_OUTPUT_BYTES and r['input_uncompressed_bytes']<=m.MAX_INPUT_BYTES for r in saved.values())
    print(json.dumps(dict(cases=report['case_count'],synthetic_internal_pass=report['internally_complete_synthetic_cases'],
        historical=report['case_reports']['historical_september_3']['summary'],trusted_live_feasible=False,formal_credit=0),indent=2))

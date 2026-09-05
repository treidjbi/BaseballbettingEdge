"""New acceptance for the paired signed-score implementation; preserves old packets."""
from __future__ import annotations
import argparse
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
from analytics.diagnostics import forward_pregame_evidence_validator as v
from market_infra.alternative_pick_evaluation_proof_v2 import validate_evaluation_proof_v2

BASELINE = '2129a9a7'
IMPLEMENTATION = 'b08284fd'
PYTHON_READER = 'market_infra/alternative_pick_evaluation_proof_v2.py'
JS_READER = 'netlify/functions/alternative-picks.mjs'
OLD = ROOT/'docs/research/evidence/2026-09-04-forward-evidence-validator'


def git_bytes(ref, path):
    return subprocess.run(['git', 'show', f'{ref}:{path}'], cwd=ROOT, capture_output=True, check=True).stdout


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def run():
    cases, probe = runpy.run_path(str(OLD/'reproduce.py'))['build_inputs']()
    cases['negative_proxy_signed_supported'] = cases.pop('negative_proxy_existing_v2_limit')
    positives = {'toward_path_b_fallback','against_path_a','mixed_market','neutral_market',
                 'under_real_splits','mixed_splits','known_no_lineup','identical_retry',
                 'negative_proxy_signed_supported'}
    reports = {name: v.validate_packet(packet) for name, packet in cases.items()}
    for name, report in reports.items():
        assert report['summary']['eligible_input_candidates'] == int(name in positives), (name,report)
        assert report['formal_prospective_credit'] == 0
    assert probe['score'] == -1 and probe['label'] == 'weak_preclose_clv_proxy'
    reference = v.reference_manifest()
    old_reference = json.loads((OLD/'run/inactive-reference-manifest.json').read_text())
    changes = {p: dict(before=old_reference['dependencies'][p], after=d)
               for p, d in reference['dependencies'].items() if old_reference['dependencies'][p] != d}
    assert set(changes) == {PYTHON_READER}, changes
    assert {k:x for k,x in reference.items() if k!='dependencies'} == {k:x for k,x in old_reference.items() if k!='dependencies'}
    assert all(x is None for x in reference['activation'].values())
    # Immutable evidence bytes, including old scripts/notebooks, must still
    # match their committed baseline. Source changes never rewrite old results.
    preserved = {}
    for dirname in ['2026-09-04-signed-score-proof-review', '2026-09-04-forward-evidence-validator', '2026-09-04-decision-time-adapter', '2026-09-04-research-lineage']:
        directory = ROOT/'docs/research/evidence'/dirname
        tracked = subprocess.run(['git','ls-tree','-r','--name-only',BASELINE,'--',str(directory.relative_to(ROOT))],cwd=ROOT,text=True,capture_output=True,check=True).stdout.splitlines()
        for path in tracked:
            raw = (ROOT/path).read_bytes()
            assert raw == git_bytes(BASELINE,path), path
            preserved[path] = sha(raw)
    old_cases = json.loads(gzip.decompress((OLD/'run/synthetic-inputs.json.gz').read_bytes()))
    old_reports = {name:v.validate_packet(packet) for name,packet in old_cases.items()}
    assert all('dependency_drift' in r['manifest_reasons'] and r['summary']['eligible_input_candidates']==0 and r['formal_prospective_credit']==0 for r in old_reports.values())
    for name, packet in cases.items():
        if name != 'negative_proxy_signed_supported':
            assert [e['frozen'] for e in packet['envelopes']] == [e['frozen'] for e in old_cases[name]['envelopes']], name
    frozen_path = ROOT/'docs/research/evidence/2026-09-04-decision-time-adapter/frozen-source.json.gz'
    frozen = json.loads(gzip.decompress(frozen_path.read_bytes()))['rows']
    assert len(frozen)==327
    assert all(validate_evaluation_proof_v2(proof=r['evaluation_proof'], row=r)==(True,()) for r in frozen)
    assert all(r['evaluation_proof']['preclose']['freshness_status']=='pending' for r in frozen)
    legacy = v.validate_packet(dict(records=frozen))
    assert legacy['summary']['legacy_rows_rejected']==327 and legacy['formal_prospective_credit']==0
    adapter = runpy.run_path(str(frozen_path.parent/'reproduce.py'))['verify']()
    sizes = {name: dict(envelope_bytes=len(v.canonical(packet['envelopes'][0])),
                       snapshot_receipts=len(packet['envelopes'][0]['market_proof']['snapshots']),
                       artifact_receipt_bytes=len(v.canonical(packet['envelopes'][0]['artifact_proof'])))
             for name,packet in cases.items() if packet['envelopes']}
    archived_artifacts = json.loads(gzip.decompress((ROOT/'docs/research/evidence/2026-09-04-research-lineage/served-artifacts.json.gz').read_bytes()))
    artifact_sizes = [len(v.canonical(r['payload'])) for r in archived_artifacts]
    historical_size_proxy = dict(records=len(artifact_sizes), minimum_bytes=min(artifact_sizes),
        maximum_bytes=max(artifact_sizes), total_bytes=sum(artifact_sizes),
        representation='canonical_reserialization_of_decoded_historical_payloads_not_original_wire_bytes')
    implementation = subprocess.run(['git','rev-parse',IMPLEMENTATION],cwd=ROOT,text=True,capture_output=True,check=True).stdout.strip()
    readers = {p:sha((ROOT/p).read_bytes()) for p in [PYTHON_READER,JS_READER]}
    assert all((ROOT/p).read_bytes()==git_bytes(IMPLEMENTATION,p) for p in readers)
    report = dict(mode='feature_branch_implementation_acceptance', implementation_commit=implementation,
        real_capture_active=False, formal_prospective_credit=0, case_count=20,
        accepted_synthetic_input_cases=9, dependency_changes=changes, paired_reader_sha256=readers,
        case_reports=reports, negative_score=probe, historical_frozen=dict(rows=327,valid=327,pending=327,credit=0),
        legacy_adapter_summary=adapter['summary'], preserved_file_sha256=preserved,
        prior_packet_revalidation=dict(cases=20,dependency_drift=20,eligible_input_candidates=0,formal_prospective_credit=0),
        synthetic_serialized_sizes=sizes, historical_artifact_size_proxy=historical_size_proxy)
    return cases, report, reference


if __name__ == '__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--create',action='store_true');args=parser.parse_args()
    cases, report, reference=run()
    if args.create:
        out=HERE/'run';out.mkdir(exist_ok=False)
        (out/'synthetic-inputs.json.gz').write_bytes(gzip.compress(v.canonical(cases),mtime=0))
        (out/'acceptance.json').write_text(json.dumps(report,sort_keys=True,indent=2)+'\n')
        (out/'inactive-reference-manifest.json').write_text(json.dumps(reference,sort_keys=True,indent=2)+'\n')
    else:
        assert cases==json.loads(gzip.decompress((HERE/'run/synthetic-inputs.json.gz').read_bytes()))
        assert report==json.loads((HERE/'run/acceptance.json').read_text())
        assert reference==json.loads((HERE/'run/inactive-reference-manifest.json').read_text())
    print(json.dumps({k:report[k] for k in ['implementation_commit','case_count','accepted_synthetic_input_cases','historical_frozen','prior_packet_revalidation','real_capture_active','formal_prospective_credit']},indent=2))

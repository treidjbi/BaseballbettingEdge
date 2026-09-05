from __future__ import annotations
import copy
import importlib
import json
from pathlib import Path
import runpy

import pytest
from analytics.diagnostics import forward_pregame_evidence_validator as v

f = runpy.run_path(str(Path(__file__).with_name('forward_capture_factory.py')))
build = f['source_bundle']


def module():
    return importlib.import_module('analytics.diagnostics.forward_capture_feasibility')


@pytest.mark.parametrize('kwargs', [{},dict(agreement='neutral'),dict(agreement='against'),
    dict(coverage='none'),dict(coverage='mixed'),dict(edge=.21,probability=.65,adjusted_ev=.4)])
def test_complete_pregame_inputs_need_no_outcomes_or_activation(kwargs):
    source=build(**kwargs);before=copy.deepcopy(source)
    report,packet=module().assess(source)
    assert report['summary']['internally_complete_inputs']==1,report
    assert report['summary']['known_rule_matches']==1
    assert report['formal_prospective_credit']==0 and report['trusted_live_feasible'] is False
    assert all(x is None for x in packet['manifest']['activation'].values())
    assert source==before


@pytest.mark.parametrize('change,reason',[
    ('late_snapshot','snapshot_receipt_after_lock'), ('seed_missing','missing_seed'),
    ('recovered','seed_not_original'), ('quote','lock_quote_mismatch'),
    ('cap','snapshot_page_cap_reached'), ('provider','provider_run_read_incomplete'),
    ('replay','market_or_decision_replay_mismatch'),('capture_missing','missing_capture'),
    ('frozen_missing','missing_frozen'), ('conflict','conflicting_capture'),
    ('seed_run','seed_run_provenance_missing'), ('activated','activation_must_be_unset'),
    ('scope','source_scope_incomplete'), ('duplicate_id','ambiguous_frozen_id'),
])
def test_exclusions(change,reason):
    b=build(); c=b['captures'][0]
    if change=='late_snapshot': c['market_proof']['snapshots'][0]['acquired_at']='2026-09-06T20:11:00+00:00'
    elif change=='seed_missing': b['attachments']=[a for a in b['attachments'] if a['kind']!='seed']
    elif change in {'recovered','seed_run'}:
        a=next(a for a in b['attachments'] if a['kind']=='seed');d=v.decode_receipt(a['receipt'])
        if change=='recovered':d['recovery_status']='recovered'
        else:d.pop('source_run_id',None)
        a['receipt']=f['factory']['receipt'](d,'2026-09-06T20:12:00+00:00',name='seed')
    elif change=='quote':b['lock_rows'][0]['locked_book']='draftkings'
    elif change in {'cap','provider'}:
        d=v.decode_receipt(c['market_proof']['read'])
        if change=='cap':d['page_row_counts']=[1000]*5
        else:d['provider_run_read_complete']=False
        c['market_proof']['read']=f['factory']['receipt'](d,f['factory']['LOCK'],name='read-completion')
    elif change=='replay': c['market_proof']['snapshots'][0]=f['factory']['receipt'](
        dict(v.decode_receipt(c['market_proof']['snapshots'][0]),american_odds=128),
        '2026-09-06T20:08:00+00:00',event_at='2026-09-06T20:00:00+00:00',name='changed-snapshot')
    elif change=='capture_missing': b['captures']=[]
    elif change=='frozen_missing':b['frozen_rows']=[];b['source_scope']['frozen_count']=0
    elif change=='conflict':b['captures'].append(copy.deepcopy(c));b['captures'][1]['provenance']['capture_run_id']='conflict'
    elif change=='activated':b['manifest']['activation']['activated_at']='2026-09-05T00:00:00+00:00'
    elif change=='scope':b['source_scope']['complete']=False
    elif change=='duplicate_id':b['frozen_rows'].append(copy.deepcopy(b['frozen_rows'][0]));b['source_scope']['frozen_count']=2
    report,_=module().assess(b)
    assert report['summary']['internally_complete_inputs']==0
    assert reason in report['attempt_reasons']+[r for row in report['records'] for r in row['reasons']],report


def test_identical_retry_keeps_one_inventory_record():
    b=build();b['captures']*=2
    report,packet=module().assess(b)
    assert len(report['records'])==len(packet['envelopes'])==1
    assert report['summary']['internally_complete_inputs']==1


def test_count_and_size_caps_stop_entire_attempt(monkeypatch):
    m=module();b=build();monkeypatch.setattr(m,'MAX_CANDIDATES',0)
    report,packet=m.assess(b)
    assert report['summary']['internally_complete_inputs']==0 and not packet['envelopes']
    assert 'candidate_cap_exceeded' in report['attempt_reasons']
    monkeypatch.setattr(m,'MAX_CANDIDATES',32);monkeypatch.setattr(m,'MAX_ENVELOPE_BYTES',100)
    report,packet=m.assess(b)
    assert report['summary']['internally_complete_inputs']==0 and not packet['envelopes']
    assert 'envelope_cap_exceeded' in report['attempt_reasons']


def test_atomic_completion_and_no_overwrite(tmp_path):
    m=module();src=tmp_path/'source.json';src.write_bytes(v.canonical(build()))
    dest=tmp_path/'out';m.run_file(src,dest)
    complete=m.read_completed(dest)
    assert complete['complete'] is True
    with pytest.raises(FileExistsError):m.run_file(src,dest)
    (dest/'report.json').write_text('{}')
    with pytest.raises(ValueError,match='digest'):m.read_completed(dest)


def test_crash_never_leaves_completed_marker(tmp_path,monkeypatch):
    m=module();src=tmp_path/'source.json';src.write_bytes(v.canonical(build()))
    original=m._atomic_file
    def crash(dest,name,body):
        if name=='packet.json':raise OSError('simulated crash')
        original(dest,name,body)
    monkeypatch.setattr(m,'_atomic_file',crash)
    with pytest.raises(OSError):m.run_file(src,tmp_path/'out')
    assert not (tmp_path/'out/COMPLETED.json').exists()
    with pytest.raises(FileExistsError):m.run_file(src,tmp_path/'out')


def test_output_cap_is_reported_without_truncated_envelope(tmp_path,monkeypatch):
    m=module();src=tmp_path/'source.json';src.write_bytes(v.canonical(build()))
    monkeypatch.setattr(m,'MAX_OUTPUT_BYTES',10000)
    m.run_file(src,tmp_path/'out')
    report=json.loads((tmp_path/'out/report.json').read_text())
    assert 'output_cap_exceeded' in report['attempt_reasons']
    assert report['summary']['internally_complete_inputs']==0
    assert not (tmp_path/'out/packet.json').exists()


def test_input_cap_and_repository_path_guard(tmp_path,monkeypatch):
    m=module();src=tmp_path/'source.json';src.write_bytes(v.canonical(build()))
    with pytest.raises(ValueError,match='research output'):m.run_file(src,m.ROOT/'data/capture-test-forbidden')
    monkeypatch.setattr(m,'MAX_INPUT_BYTES',10)
    with pytest.raises(ValueError,match='input_cap'):m.run_file(src,tmp_path/'out')
    assert not (tmp_path/'out').exists()


@pytest.mark.parametrize('field',['result','selector_override','settlement'])
def test_extra_capture_fields_are_not_silently_dropped(field):
    b=build();b['captures'][0][field]='unexpected'
    r,_=module().assess(b)
    assert r['summary']['internally_complete_inputs']==0
    assert 'capture_source_schema_drift' in r['records'][0]['reasons']


def test_wrong_same_candidate_attachment_identity_fails_closed():
    b=build();a=copy.deepcopy(b['attachments'][0]);a['identity']['lock_id']='wrong-lock';b['attachments'].append(a)
    r,_=module().assess(b)
    assert 'attachment_identity_mismatch' in r['attempt_reasons']
    assert r['summary']['internally_complete_inputs']==0


def test_historical_outcome_does_not_supply_original_seed():
    b=build();b['evidence_kind']='historical'
    b['attachments']=[a for a in b['attachments'] if a['kind']!='seed']
    r,_=module().assess(b)
    assert r['summary']['pregame_internal_valid']==1
    assert r['summary']['internally_complete_inputs']==0


def test_external_source_strings_are_never_fetched(tmp_path,monkeypatch):
    import requests
    def forbidden(*a,**kw):raise AssertionError('Network forbidden in offline capture')
    monkeypatch.setattr(requests.sessions.Session,'request',forbidden)
    b=build();b['captures'][0]['market_proof']['snapshots'][0]['source_path']='https://example.invalid/do-not-fetch'
    src=tmp_path/'source.json';src.write_bytes(v.canonical(b))
    assert module().run_file(src,tmp_path/'out')['summary']['internally_complete_inputs']==1


def test_actual_33_candidate_inventory_is_not_truncated():
    b=build()
    for i in range(32):
        lock=copy.deepcopy(b['lock_rows'][0]);lock.update(id=f'additional-{i}',normalized_pitcher=f'synthetic pitcher {i}')
        b['lock_rows'].append(lock)
    b['source_scope']['lock_count']=33
    report,packet=module().assess(b)
    assert len(report['records'])==len(packet['inventory'])==33
    assert report['summary']['internally_complete_inputs']==0
    assert 'candidate_cap_exceeded' in report['attempt_reasons']


def test_seed_event_cannot_predate_its_locked_quote_witness():
    b=build();a=next(a for a in b['attachments'] if a['kind']=='seed')
    a['receipt']['source_event_at']='2026-09-06T19:59:00+00:00'
    r,_=module().assess(b)
    assert r['summary']['internally_complete_inputs']==0
    assert 'seed_witness_before_consumption' in r['records'][0]['reasons']


def test_favorable_or_selected_status_is_not_an_inventory_filter(monkeypatch):
    m=module();original=m.v._pregame
    def nonmatch(*args):return dict(original(*args),selector_match=False)
    monkeypatch.setattr(m.v,'_pregame',nonmatch)
    report,_=m.assess(build())
    assert report['summary']['known_rule_matches']==0
    assert report['summary']['internally_complete_inputs']==1

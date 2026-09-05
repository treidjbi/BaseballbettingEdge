from __future__ import annotations
import copy
import importlib
import json
from pathlib import Path
import pytest
import runpy
_factory = runpy.run_path(str(Path(__file__).with_name("forward_evidence_factory.py")))
build_case, receipt, DATE, GAME, LOCK = (_factory[k] for k in ("build_case", "receipt", "DATE", "GAME", "LOCK"))


def module():
    return importlib.import_module('analytics.diagnostics.forward_pregame_evidence_validator')


def result(packet):
    return module().validate_packet(packet)


def reseal(packet):
    env=packet['envelopes'][0]
    module().seal(env)
    for a in packet['attachments']: a['envelope_sha256']=env['content_sha256']


def test_complete_synthetic_acceptance_never_grants_formal_credit():
    p=build_case(); before=copy.deepcopy(p); r=result(p)
    assert r['records'][0]['pregame_valid'] is True, r
    assert r['records'][0]['eligible_input_candidate'] is True, r
    assert r['formal_prospective_credit']==0
    assert p==before


@pytest.mark.parametrize('agreement',['toward','against','mixed','neutral'])
@pytest.mark.parametrize('path_mode',['path_a','path_b'])
def test_known_agreement_and_fallback_are_not_positive_filters(agreement,path_mode):
    r=result(build_case(agreement,path_mode))['records'][0]
    assert r['pregame_valid'] is True, r
    assert r['selector_match'] is True
    assert r['eligible_input_candidate'] is True


def test_inactive_manifest_is_diagnostic():
    r=result(build_case(activated=False))
    assert r['records'][0]['pregame_valid']
    assert not r['records'][0]['eligible_input_candidate']
    assert 'activation_unset' in r['manifest_reasons']


@pytest.mark.parametrize('minutes,valid',[(15,False),(15.0001,True),(30,True),(30.0001,False)])
def test_exact_timing_boundaries(minutes,valid):
    r=result(build_case(minutes=minutes))['records'][0]
    assert r['pregame_valid'] is valid, r


@pytest.mark.parametrize('change,reason',[
 ('late_receipt','snapshot_receipt_after_lock'),('future_artifact','artifact_receipt_after_lock'),
 ('poststart_completion','freeze_not_pregame'),('missing_path','path_b_incomplete'),
 ('negative_count','path_b_invalid_counts'),('no_signal_missing','agreement_mismatch'),
 ('quote','lock_quote_mismatch'),('book','lock_quote_mismatch'),('game','lock_identity_mismatch'),
 ('hash','artifact_byte_hash_mismatch'),('pages','market_read_incomplete'),
 ('window','market_read_incomplete'),('drift','dependency_drift'),('baseline','baseline_drift'),
 ('rule','selector_drift'),('unknown_seed','seed_not_original'),('recovered','seed_not_original'),
 ('unconsumed','missing_consumption'),('missing_close','missing_close'),
])
def test_exclusions(change,reason):
    p=build_case(); e=p['envelopes'][0]
    if change=='late_receipt': e['market_proof']['snapshots'][0]['acquired_at']=GAME
    elif change=='future_artifact': e['artifact_proof']['acquired_at']=GAME
    elif change=='poststart_completion': e['provenance']['persisted_at']=GAME
    elif change=='missing_path': e['path_b'].pop('batter_handedness_mode')
    elif change=='negative_count': e['path_b']['lineup_real_split_count']=-1
    elif change=='no_signal_missing': e['agreement']['label']='market_no_signal'
    elif change=='quote': e['lock']['locked_odds']=-101
    elif change=='book': e['lock']['locked_book']='draftkings'
    elif change=='game': e['lock']['game_time']=DATE+'T21:00:00+00:00'
    elif change=='hash': e['artifact_proof']['byte_sha256']='b'*64
    elif change in {'pages','window'}:
        r=e['market_proof']['read']; d=module().decode_receipt(r)
        if change=='pages': d.update(complete=False,reason_codes=['snapshot_page_cap_reached'])
        else: d['window_start']=LOCK
        e['market_proof']['read']=receipt(d,LOCK)
    elif change=='drift': p['manifest']['dependencies']['market_infra/alternative_pick_preclose_v2.py']='b'*64
    elif change=='baseline': p['manifest']['baselines']['historical']['pnl']=99
    elif change=='rule': p['manifest']['selector_fingerprint']='b'*64
    elif change in {'unknown_seed','recovered'}:
        a=next(a for a in p['attachments'] if a['kind']=='seed');d=module().decode_receipt(a['receipt']);d['recovery_status']='unknown' if change=='unknown_seed' else 'recovered';a['receipt']=receipt(d,DATE+'T20:12:00+00:00')
    elif change=='unconsumed': p['attachments']=[a for a in p['attachments'] if a['kind']!='consumption']
    elif change=='missing_close': p['attachments']=[a for a in p['attachments'] if a['kind']!='close']
    reseal(p);r=result(p)
    assert not r['records'][0]['eligible_input_candidate']
    assert reason in r['records'][0]['reasons']+r['manifest_reasons'],r


def test_result_changes_do_not_change_pregame_selection():
    p=build_case();before=result(p)['records'][0]
    for a in p['attachments']:
        if a['kind']=='settlement':
            d=module().decode_receipt(a['receipt']);d.update(result='win',pnl=1.28)
            a['receipt']=receipt(d,DATE+'T23:00:00+00:00')
    after=result(p)['records'][0]
    for field in ['pregame_valid','selector_match','decision_digest']: assert before[field]==after[field]


def test_duplicate_retry_and_conflict():
    p=build_case();p['envelopes'].append(copy.deepcopy(p['envelopes'][0]))
    r=result(p);assert len(r['records'])==1 and r['records'][0]['pregame_valid']
    p['envelopes'][1]['provenance']['capture_run_id']='changed';module().seal(p['envelopes'][1])
    assert 'conflicting_retry' in result(p)['records'][0]['reasons']


def test_capture_inventory_missing_row_is_not_dropped():
    p=build_case();p['envelopes']=[]
    r=result(p);assert r['summary']['missing_capture']==1
    assert r['formal_prospective_credit']==0


def test_legacy_adapter_rows_receive_no_credit():
    p={'schema':'decision_time_linkage_v1','records':[{'selector_match':True}]*19}
    r=result(p);assert r['formal_prospective_credit']==0
    assert r['summary']['legacy_rows_rejected']==19


def test_cli_new_output_only(tmp_path):
    p=tmp_path/'input.json';p.write_text(json.dumps(build_case()))
    args=['--input',str(p),'--output-dir',str(tmp_path/'output')]
    assert module().main(args)==0
    with pytest.raises(FileExistsError): module().main(args)


def test_no_network_or_writer_import_in_fresh_process():
    import subprocess,sys
    code="import sys; import analytics.diagnostics.forward_pregame_evidence_validator; assert not any('supabase_writer' in x or 'alternative_pick_recording' in x or 'post_grading_shadow' in x for x in sys.modules)"
    assert subprocess.run([sys.executable,'-c',code]).returncode==0


def change_receipt(p, path, transform):
    obj=p['envelopes'][0]
    for k in path[:-1]: obj=obj[k]
    old=obj[path[-1]];d=module().decode_receipt(old);transform(d)
    obj[path[-1]]=receipt(d,old['acquired_at'],event_at=old['source_event_at'],name=old['receipt_id'])
    reseal(p)


def test_window_from_another_candidate_is_rejected():
    p=build_case()
    change_receipt(p,['market_proof','windows'],lambda d:d.update(candidate_identity='f'*64))
    assert 'window_binding_mismatch' in result(p)['records'][0]['reasons']


def test_original_seed_requires_explicit_null_result():
    p=build_case();a=next(a for a in p['attachments'] if a['kind']=='seed')
    d=module().decode_receipt(a['receipt']);d.pop('result');a['receipt']=receipt(d,DATE+'T20:12:00+00:00')
    assert 'seed_not_original' in result(p)['records'][0]['reasons']


def test_contradictory_recovery_metadata_is_excluded():
    p=build_case();a=next(a for a in p['attachments'] if a['kind']=='seed')
    d=module().decode_receipt(a['receipt']);d['archive_outcome_reconciliation_source']='picks_history_exact'
    a['receipt']=receipt(d,DATE+'T20:12:00+00:00')
    assert 'seed_not_original' in result(p)['records'][0]['reasons']


def test_close_cannot_be_relabelled_without_changing_its_quote():
    p=build_case();a=next(a for a in p['attachments'] if a['kind']=='close')
    d=module().decode_receipt(a['receipt']);d['clv_type']='price_only';a['receipt']=receipt(d,DATE+'T23:00:00+00:00')
    assert 'close_bucket_mismatch' in result(p)['records'][0]['reasons']


@pytest.mark.parametrize('field,value,reason',[
 ('closing_book','draftkings','close_attribution_missing'),
 ('closing_provider','boltodds','close_attribution_missing'),
 ('closing_odds',0,'close_attribution_missing'),
])
def test_close_requires_exact_attribution(field,value,reason):
    p=build_case();a=next(a for a in p['attachments'] if a['kind']=='close')
    d=module().decode_receipt(a['receipt']);d[field]=value;a['receipt']=receipt(d,DATE+'T23:00:00+00:00')
    assert reason in result(p)['records'][0]['reasons']


def test_lock_source_path_must_match_acquired_body():
    p=build_case();p['envelopes'][0]['lock']['source_artifact_path']='wrong://body';reseal(p)
    assert 'lock_artifact_path_mismatch' in result(p)['records'][0]['reasons']


def test_copied_snapshot_deliveries_do_not_add_maturity():
    p=build_case();mp=p['envelopes'][0]['market_proof'];mp['snapshots'].append(copy.deepcopy(mp['snapshots'][0]));reseal(p)
    assert 'duplicate_snapshot_delivery' in result(p)['records'][0]['reasons']


def test_same_time_observations_are_immature():
    p=build_case();mp=p['envelopes'][0]['market_proof'];d=module().decode_receipt(mp['snapshots'][1]);d['observed_at']=DATE+'T20:00:00+00:00'
    mp['snapshots'][1]=receipt(d,event_at=d['observed_at']);reseal(p)
    assert any('market_pending' in r for r in result(p)['records'][0]['reasons'])


def test_nonfinite_input_fails_read():
    p=build_case();p['envelopes'][0]['decision_time']['edge']=float('nan')
    with pytest.raises(ValueError):result(p)


def test_duplicate_json_keys_fail_read():
    with pytest.raises(ValueError):module().loads('{"schema":1,"schema":2}')


def test_conflicting_attachment_is_not_latest_winner():
    p=build_case();a=copy.deepcopy(p['attachments'][0]);a['receipt']['receipt_id']='second';p['attachments'].append(a)
    assert 'conflicting_consumption' in result(p)['records'][0]['reasons']


def test_orphan_attachment_is_visible_and_blocks_eligibility():
    p=build_case();a=copy.deepcopy(p['attachments'][0]);a['envelope_sha256']='f'*64;p['attachments'].append(a)
    r=result(p);assert 'orphan_attachment' in r['manifest_reasons'];assert not r['records'][0]['eligible_input_candidate']


def test_false_persisted_digest_is_excluded():
    p=build_case();p['envelopes'][0]['decision_time']['edge']=.3
    assert 'envelope_digest_mismatch' in result(p)['records'][0]['reasons']


def test_naive_receipt_timestamp_is_excluded():
    p=build_case();p['envelopes'][0]['artifact_proof']['acquired_at']=DATE+'T20:05:30';reseal(p)
    assert 'invalid_timestamp' in result(p)['records'][0]['reasons']


def test_old_capture_cannot_be_activated_retroactively():
    p=build_case();p['manifest']['activation']['first_unobserved_slate']='2026-09-07';e=p['envelopes'][0];e['manifest_sha256']=module().digest(p['manifest']);reseal(p)
    assert 'before_activation' in result(p)['records'][0]['reasons']


def test_blocked_market_keeps_known_frozen_selector_match():
    p=build_case();p['envelopes'][0]['market_proof']['snapshots'][0]['acquired_at']=GAME;reseal(p)
    r=result(p)['records'][0]
    assert r['selector_match'] is True and not r['pregame_valid']


@pytest.mark.parametrize('coverage',['real','mixed','fallback','none'])
@pytest.mark.parametrize('side',['over','under'])
def test_known_coverage_and_both_sides(coverage,side):
    r=result(build_case(coverage=coverage,side=side))['records'][0]
    assert r['pregame_valid'] and r['eligible_input_candidate'],r


def test_complete_negative_score_is_known_weak_evidence_without_formal_credit():
    p=build_case(edge=.21,probability=.65,adjusted_ev=.4)
    report=result(p); r=report['records'][0]
    assert r['eligible_input_candidate'], r
    assert p['envelopes'][0]['preclose']==dict(status='known',label='weak_preclose_clv_proxy',score=-1)
    assert report['formal_prospective_credit']==0


def test_extra_outcome_fields_cannot_enter_frozen_envelope():
    p=build_case();p['envelopes'][0]['result']='win';reseal(p)
    assert 'envelope_schema_drift' in result(p)['records'][0]['reasons']


def test_freeze_row_cannot_exist_after_envelope_completion():
    p=build_case();p['envelopes'][0]['frozen']['inserted_at']=DATE+'T20:15:00+00:00';reseal(p)
    assert 'freeze_not_pregame' in result(p)['records'][0]['reasons']


def test_artifact_tracked_game_cannot_conflict_with_pitcher():
    p=build_case();e=p['envelopes'][0]
    # Rebinding all artifact digests is intentionally not done: even a simple
    # altered source body must fail; a separate game check precedes replay.
    change_receipt(p,['artifact_proof'],lambda d:d['pitchers'][0]['tracked_picks'][0].update(game_time=DATE+'T22:00:00+00:00'))
    assert not result(p)['records'][0]['pregame_valid']


def test_existing_clv_price_and_line_bucket_is_preserved():
    p=build_case();a=next(a for a in p['attachments'] if a['kind']=='close')
    d=module().decode_receipt(a['receipt']);d.update(closing_line=4.5,closing_odds=120,clv_type='price_and_line')
    a['receipt']=receipt(d,DATE+'T23:00:00+00:00')
    assert result(p)['records'][0]['eligible_input_candidate']


def test_reused_lock_identifier_quarantines_both_candidates():
    p=build_case();second=copy.deepcopy(p['envelopes'][0]);second['identity']['normalized_pitcher']='other pitcher';module().seal(second)
    p['envelopes'].append(second);p['inventory'].append(dict(identity=second['identity'],status='captured'))
    assert all('reused_source_id' in r['reasons'] for r in result(p)['records'])


def test_capture_failure_preserves_declared_reason():
    p=build_case();p['envelopes']=[];p['inventory'][0].update(status='failed',reasons=['snapshot_page_cap_reached'])
    r=result(p)['records'][0];assert r['capture_context'][0]['reasons']==['snapshot_page_cap_reached']


@pytest.mark.parametrize('result_value',['push','void'])
def test_pushes_and_voids_are_visible_but_not_counted(result_value):
    p=build_case();a=next(a for a in p['attachments'] if a['kind']=='settlement')
    d=module().decode_receipt(a['receipt']);d.update(result=result_value,pnl=0);a['receipt']=receipt(d,DATE+'T23:00:00+00:00')
    r=result(p)['records'][0];assert r['pregame_valid'];assert not r['eligible_input_candidate']
    assert 'settlement_not_win_loss' in r['reasons']
    assert r['outcome_context']['result']==result_value


def test_cli_malformed_input_does_not_create_output(tmp_path):
    p=tmp_path/'bad.json';p.write_text('{"manifest":null,"envelopes":"invalid"}')
    with pytest.raises((ValueError,KeyError,TypeError)):
        module().main(['--input',str(p),'--output-dir',str(tmp_path/'output')])
    assert not (tmp_path/'output').exists()


def test_canonical_paths_are_never_writable(tmp_path):
    p=tmp_path/'valid.json';p.write_text(json.dumps(build_case()))
    with pytest.raises(ValueError):
        module().main(['--input',str(p),'--output-dir',str(module().ROOT/'data/research/gate_c/forbidden')])

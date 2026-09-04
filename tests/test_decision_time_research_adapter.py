from __future__ import annotations

import copy
import gzip
import importlib
import json
from pathlib import Path

import pytest


FIXTURE = Path(__file__).parent / 'fixtures' / 'decision_time_research_adapter.json'


@pytest.fixture
def data():
    return json.loads(FIXTURE.read_text())


def module():
    return importlib.import_module('analytics.diagnostics.decision_time_research_adapter')


def packet(data, **overrides):
    args = dict(gate_c_rows=[data['gate_c']], lock_rows=[data['lock']],
                frozen_rows=[data['frozen']], start_date='2026-08-15', end_date='2026-09-03')
    args.update(overrides)
    return module().build_packet(**args)


def test_exact_link_preserves_separate_sources_and_never_grants_credit(data):
    original = copy.deepcopy(data)
    out = packet(data)
    row = out['records'][0]
    assert row['linkage_status'] == 'linked'
    assert row['decision_input_status'] == 'validated'
    assert row['selector_match'] is True
    assert row['formal_prospective_credit'] is False
    assert out['summary']['formal_prospective_credit'] == 0
    assert row['decision_time']['official_line_source_provider'] == 'therundown'
    assert row['lock_proof']['source_artifact_path'] == data['lock']['source_artifact_path']
    assert row['archive_context']['source_artifact_path'] == data['gate_c']['source_artifact_path']
    assert 'market_agreement_unavailable' in row['evidence_gaps']
    assert 'preclose_unavailable' in row['evidence_gaps']
    assert 'frozen_path_b_unavailable' in row['evidence_gaps']
    assert data == original


def test_archive_and_outcome_changes_cannot_change_frozen_selection(data):
    before = packet(data)['records'][0]
    data['gate_c'].update(quality_gate_level='clean', model_market_relationship='unknown',
                         result='loss', pick_history_pnl=-1, provider='propline',
                         market_agreement_label='market_with_model', preclose_clv_proxy_label='strong_preclose_clv_proxy')
    after = packet(data)['records'][0]
    assert after['decision_time'] == before['decision_time']
    assert after['selector_match'] == before['selector_match'] is True
    assert after['pregame_evidence'] == before['pregame_evidence']
    assert after['archive_context']['quality_gate_level'] == 'clean'
    assert after['outcome_context']['pick_history_pnl'] == -1


@pytest.mark.parametrize('source,field,value,reason', [
    ('lock','consumed_at',None,'unconsumed_lock'),
    ('lock','locked_odds',-101,'lock_frozen_quote_mismatch'),
    ('lock','locked_k_line',9.5,'lock_frozen_quote_mismatch'),
    ('lock','locked_verdict','FIRE 2u','lock_frozen_quote_mismatch'),
    ('lock','game_time','2026-08-16T03:00:00Z','lock_frozen_time_mismatch'),
    ('lock','source_artifact_sha256','a'*64,'lock_frozen_hash_mismatch'),
    ('gate_c','bet_time_book','Other Book','archive_lock_book_mismatch'),
    ('gate_c','bet_time_line',9.5,'archive_lock_quote_mismatch'),
    ('gate_c','bet_time_odds',-101,'archive_lock_quote_mismatch'),
    ('gate_c','bet_time_at','2026-08-15T00:00:00Z','archive_lock_time_mismatch'),
    ('gate_c','game_time','2026-08-16T03:00:00Z','archive_lock_time_mismatch'),
    ('frozen','inserted_at','2026-08-16T23:00:00Z','freeze_not_prospective'),
    ('frozen','frozen_at','2026-08-16T23:00:00Z','freeze_not_prospective'),
    ('frozen','checkpoint','provisional','not_frozen_pregame'),
])
def test_conflicts_are_explicit_exclusions(data, source, field, value, reason):
    data[source][field] = value
    row = packet(data)['records'][0]
    assert row['linkage_status'] == 'excluded'
    assert reason in row['exclusion_reasons']
    assert row['formal_prospective_credit'] is False


@pytest.mark.parametrize('arg,source,reason', [
    ('gate_c_rows','gate_c','duplicate_gate_c_identity'),
    ('lock_rows','lock','duplicate_lock_identity'),
    ('frozen_rows','frozen','duplicate_frozen_identity'),
])
def test_duplicates_do_not_choose_a_winner(data, arg, source, reason):
    result = packet(data, **{arg:[data[source],copy.deepcopy(data[source])]})
    assert result['records'][0]['linkage_status'] == 'excluded'
    assert reason in result['records'][0]['exclusion_reasons']


@pytest.mark.parametrize('arg,reason', [('gate_c_rows','missing_gate_c'),('lock_rows','missing_lock'),('frozen_rows','missing_frozen')])
def test_missing_sources_are_not_filled(data, arg, reason):
    row = packet(data, **{arg:[]})['records'][0]
    assert row['linkage_status'] == 'excluded'
    assert reason in row['exclusion_reasons']


@pytest.mark.parametrize('field,value', [('quality_gate_level',None),('model_market_relationship','unknown'),('edge',float('nan'))])
def test_incomplete_or_invalid_proof_cannot_use_archive_fallback(data, field, value):
    data['frozen']['evaluation_proof']['normalized_inputs'][field] = value
    row = packet(data)['records'][0]
    assert row['decision_input_status'] == 'excluded'
    assert row['selector_match'] is None
    assert row['decision_time'] is None


def test_recovered_archive_is_quarantined(data):
    data['gate_c']['archive_outcome_reconciliation_source'] = 'picks_history_exact'
    row = packet(data)['records'][0]
    assert 'history_recovered' in row['exclusion_reasons']
    assert row['linkage_status'] == 'excluded'


def test_injected_postlock_preclose_cannot_be_accepted(data):
    preclose = data['frozen']['evaluation_proof']['preclose']
    preclose.update(freshness_status='fresh',label='strong_preclose_clv_proxy',
                    last_observed_at=data['frozen']['game_time'])
    row = packet(data)['records'][0]
    assert row['decision_input_status'] == 'excluded'
    assert row['pregame_evidence']['preclose'] is None


@pytest.mark.parametrize('fields,expected', [
    ({'official_line_source_provider':'therundown','provider':'propline'},'therundown'),
    ({'official_odds_source':'propline'},'propline'),
    ({'official_odds_source':'therundown+propline','provider':'therundown'},None),
    ({'official_line_source_provider':'unknown','official_odds_source':'propline'},None),
    ({'provider':'therundown','live_display_provider':'propline','odds_source':'therundown'},None),
])
def test_official_provider_reader_does_not_infer_from_movement(fields, expected):
    assert module().explicit_official_provider(fields) == expected


def test_deterministic_packet_and_bounded_dates(data):
    assert packet(data) == packet(data)
    out = packet(data,start_date='2026-09-01',end_date='2026-09-03')
    assert out['records'] == []
    with pytest.raises(ValueError):
        packet(data,start_date='2026-09-04',end_date='2026-09-03')


def test_cli_gzip_and_no_overwrite(tmp_path, data):
    for name,rows in [('gate',[data['gate_c']]),('locks',[data['lock']]),('frozen',[data['frozen']])]:
        (tmp_path/(name+'.json.gz')).write_bytes(gzip.compress(json.dumps({'rows':rows}).encode()))
    dest=tmp_path/'result'
    args=['--gate-c',str(tmp_path/'gate.json.gz'),'--locks',str(tmp_path/'locks.json.gz'),
          '--frozen',str(tmp_path/'frozen.json.gz'),'--start-date','2026-08-15','--end-date','2026-09-03','--output-dir',str(dest)]
    assert module().main(args) == 0
    saved=(dest/'packet.json').read_bytes()
    assert json.loads(saved)['summary']['formal_prospective_credit'] == 0
    with pytest.raises(FileExistsError): module().main(args)
    assert (dest/'packet.json').read_bytes() == saved


def test_output_cannot_write_canonical_repo_paths(data):
    with pytest.raises(ValueError):
        module().write_packet(packet(data), module().ROOT/'data/research/gate_c/unsafe-adapter-output')


def test_malformed_identity_fails_entire_read(data):
    data['lock']['side']='garbage'
    with pytest.raises(ValueError): packet(data)


def test_lock_hash_cannot_bind_a_different_frozen_artifact(data):
    data['frozen']['lock_artifact_sha256'] = 'b' * 64
    data['lock']['source_artifact_sha256'] = 'b' * 64
    assert 'lock_frozen_hash_mismatch' in packet(data)['records'][0]['exclusion_reasons']


def test_future_artifact_cannot_supply_frozen_inputs(data):
    value = data['frozen']['game_time']
    data['frozen']['source_artifact_generated_at'] = value
    data['frozen']['evaluation_proof']['artifact']['source_artifact_generated_at'] = value
    assert 'artifact_not_available_at_freeze' in packet(data)['records'][0]['exclusion_reasons']


def test_same_lock_id_cannot_be_used_for_two_candidates(data):
    other = copy.deepcopy(data['lock'])
    other['normalized_pitcher'] = 'another pitcher'
    rows = packet(data, lock_rows=[data['lock'], other])['records']
    assert all('duplicate_lock_source_id' in r['exclusion_reasons'] for r in rows)


def test_naive_timestamp_is_not_pregame_proof(data):
    data['frozen']['inserted_at'] = '2026-08-15T19:41:07'
    assert 'freeze_not_prospective' in packet(data)['records'][0]['exclusion_reasons']


def test_symlink_cannot_bypass_canonical_output_guard(tmp_path, data):
    (tmp_path/'linked').symlink_to(module().ROOT/'data', target_is_directory=True)
    with pytest.raises(ValueError):
        module().write_packet(packet(data), tmp_path/'linked'/'adapter-forbidden')


def test_valid_fresh_proof_is_exposed_without_credit():
    data = json.loads((FIXTURE.parent/'decision_time_adapter_synthetic_fresh.json').read_text())
    row = packet(data, start_date='2026-07-22', end_date='2026-07-22')['records'][0]
    assert row['linkage_status'] == 'linked'
    assert row['pregame_evidence']['preclose'] == data['frozen']['evaluation_proof']['preclose']
    assert row['selector_match'] is False
    assert row['formal_prospective_credit'] is False


def test_valid_proof_with_observations_after_lock_is_excluded():
    data = json.loads((FIXTURE.parent/'decision_time_adapter_synthetic_fresh.json').read_text())
    early = '2026-07-22T19:58:00+00:00'
    for field in ['locked_at', 'frozen_at', 'observed_at']:
        data['frozen'][field] = early
    data['lock']['locked_at'] = early
    data['gate_c']['bet_time_at'] = early
    data['frozen']['evaluation_proof']['normalized_inputs']['observed_at'] = early
    row = packet(data, start_date='2026-07-22', end_date='2026-07-22')['records'][0]
    assert 'preclose_not_prospective' in row['exclusion_reasons']
    assert row['pregame_evidence']['preclose'] is None

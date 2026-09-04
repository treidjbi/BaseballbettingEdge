"""Synthetic acceptance inputs only. No captured or prospective observations."""
from __future__ import annotations
import base64
import copy
import hashlib
import json
from datetime import datetime, timedelta
from market_infra.alternative_pick_selection_state import candidate_record
from market_infra.alternative_pick_preclose_v2 import resolve_candidate_bindings_v2, build_exact_preclose_evidence_v2
from market_infra.alternative_pick_selector_v2 import evaluate_alternative_pick_v2
from market_infra.alternative_pick_evaluation_proof_v2 import build_evaluation_proof_v2
from market_infra.published_artifacts import canonical_payload_sha256

DATE = '2026-09-06'
LOCK = DATE+'T20:10:00+00:00'
GAME = DATE+'T20:40:00+00:00'
START = DATE+'T19:55:00+00:00'


def receipt(data, at=DATE+'T20:08:00+00:00', *, event_at=None, name='synthetic'):
    body = json.dumps(data, sort_keys=True, separators=(',', ':'), allow_nan=False).encode()
    return dict(body_base64=base64.b64encode(body).decode(), byte_sha256=hashlib.sha256(body).hexdigest(),
                acquired_at=at, source_event_at=event_at or at, receipt_id=name, source_path='synthetic://'+name)


def build_case(agreement='toward', path_mode='path_b', minutes=30, activated=True,
               side='over', coverage='fallback', edge=.035, probability=.44, adjusted_ev=.09, allow_pending=False):
    from analytics.diagnostics import forward_pregame_evidence_validator as v
    game=(datetime.fromisoformat(LOCK)+timedelta(minutes=minutes)).isoformat()
    pick=dict(pitcher='Synthetic Pitcher',side=side,display_verdict='LEAN',display_k_line=3.5,
              display_odds=128,display_book='fanduel',game_time=game,edge=edge,adj_ev=adjusted_ev,
              quality_gate_level='capped',model_win_prob=probability,raw_verdict='FIRE 2u',
              large_edge_skepticism_flag=True,market_anchor_selector={'labels':[]})
    pitcher=dict(pitcher='Synthetic Pitcher',team='ARI',opp_team='LAD',game_time=game,k_line=3.5,
        odds_source='therundown',market_source_mode='therundown',line_source_provider='therundown',
        source_current_market_line_ids=[101],best_over_odds=128,best_under_odds=-150,
        best_over_book='fanduel',best_under_book='fanduel',avg_ip=5.8,recent_start_count=5,
        season_k9=9.4,recent_k9=9.7,career_k9=9.1,is_opener=False,starter_mismatch=False,
        last_pitch_count=95,days_since_last_start=5,batter_handedness_mode=path_mode,
        lineup_used=True,lineup_count=9,lineup_real_split_count=0,lineup_path_a_fallback_count=9,
        lineup_split_source='path_a',ev_over=copy.deepcopy(pick),tracked_picks=[copy.deepcopy(pick)])
    if side=='under':
        pitcher.update(best_under_odds=128,best_over_odds=-150,ev_under=copy.deepcopy(pick))
    if coverage=='real': pitcher.update(lineup_real_split_count=9,lineup_path_a_fallback_count=0,lineup_split_source='real_split_cache')
    elif coverage=='mixed': pitcher.update(lineup_real_split_count=4,lineup_path_a_fallback_count=5,lineup_split_source='mixed_real_split_cache')
    elif coverage=='none': pitcher.update(lineup_used=False,lineup_count=0,lineup_real_split_count=0,lineup_path_a_fallback_count=0,lineup_split_source='none')
    candidate=candidate_record(slate_date=DATE,pitcher=pitcher['pitcher'],side=side,model_k_line=3.5,
        team='ARI',opp_team='LAD',game_time=game,provider_posture='therundown')
    candidate.update(official_odds=128,official_book='fanduel',official_verdict='LEAN',line_source_provider='therundown')
    snapshots=[]; lines={}
    books=['fanduel','draftkings'] if agreement=='mixed' else ['fanduel']
    for b,book in enumerate(books):
        first = 135 if agreement=='toward' or (agreement=='mixed' and b==0) else 120 if agreement in {'against','mixed'} else 128
        for j,odds in enumerate([first,128]):
            identifier=f'{b+1}{j+1}111111-1111-4111-8111-111111111111'
            row=dict(id=identifier,provider='therundown',provider_event_id='synthetic-event',slate_date=DATE,
                normalized_player_name='synthetic pitcher',player_name='Synthetic Pitcher',market_key='pitcher_strikeouts',
                bookmaker_key=book,side=side,line=3.5,american_odds=odds,game_time=game,
                observed_at=DATE+('T20:00:00+00:00' if j==0 else 'T20:06:00+00:00'))
            snapshots.append(row)
            if j==0:
                lines[str(101+b)]=dict(id=101+b,slate_date=DATE,provider='therundown',provider_event_id='synthetic-event',
                    normalized_player_name='synthetic pitcher',market_key='pitcher_strikeouts',line=3.5,game_time=game,
                    over_snapshot_id=identifier if side=='over' else None,under_snapshot_id=identifier if side=='under' else None)
    pitcher['source_current_market_line_ids']=[int(i) for i in lines]
    payload=dict(date=DATE,generated_at=DATE+'T20:05:00+00:00',pitchers=[pitcher])
    artifact=receipt(payload,DATE+'T20:05:30+00:00',event_at=payload['generated_at'],name='official-artifact')
    bindings=resolve_candidate_bindings_v2(candidate=candidate,pitcher=pitcher,current_lines_by_id=lines,snapshot_rows=snapshots)
    windows=dict(candidate_became_current_at=START,provider_window_started_at={'therundown':START},
        candidate_identity=candidate['candidate_identity'],official_binding_key=bindings['official_binding_key'],
        sidecar_binding_keys=bindings['sidecar_binding_keys'])
    exact=build_exact_preclose_evidence_v2(candidate=candidate,bindings=bindings,windows=windows,snapshot_rows=snapshots,
        provider_heartbeats=[],snapshot_read_complete=True,snapshot_window_started_at=START,
        snapshot_read_reason_codes=[],observed_at=LOCK,source_artifact_path='dashboard/data/processed/today.json',
        source_artifact_byte_sha256=artifact['byte_sha256'])
    evaluation=evaluate_alternative_pick_v2(pitcher=pitcher,pick=dict(pick,side=side,official_k_line=3.5,odds=128),
        exact_evidence=exact.market_evidence,slate_date=DATE,is_tracked=True,
        source_artifact_path='dashboard/data/processed/today.json',source_payload_sha256=canonical_payload_sha256(payload),
        source_artifact_byte_sha256=artifact['byte_sha256'],observed_at=LOCK)
    art=dict(path='dashboard/data/processed/today.json',payload=payload,payload_sha256=canonical_payload_sha256(payload),
        byte_sha256=artifact['byte_sha256'],generated_at=payload['generated_at'])
    built=build_evaluation_proof_v2(candidate=candidate,evaluation=evaluation,exact_preclose=exact,artifact=art)
    assert built.selection_safe or allow_pending, built.reason_codes
    proof=built.proof; d=proof['decision']; pre=proof['preclose']
    frozen=dict(candidate,**proof['artifact'],id='synthetic-freeze',bundle_id=proof['bundle_id'],
        selector_fingerprint=proof['selector_fingerprint'],selector_id=None,checkpoint='frozen_pregame',
        observed_at=LOCK,locked_at=LOCK,frozen_at=LOCK,inserted_at=DATE+'T20:10:01+00:00',
        lock_artifact_sha256=artifact['byte_sha256'],selection_status=d['selection_status'],lane=d['selected_lane'],
        family_count=d['family_count'],family_states=d['family_states'],evaluation_proof=proof,
        evidence_observation_ids=pre['decisive_observation_tokens'],evidence_observation_count=pre['qualifying_observation_count'],
        evidence_first_observed_at=pre['first_observed_at'],evidence_last_observed_at=pre['last_observed_at'],
        evidence_freshness_status=pre['freshness_status'])
    if d['selected_lane']:
        from market_infra.alternative_pick_selection_v2 import SELECTOR_IDS_BY_LANE
        frozen['selector_id']=SELECTOR_IDS_BY_LANE[d['selected_lane']]
    lock=dict(id='synthetic-lock',slate_date=DATE,normalized_pitcher='synthetic pitcher',side=side,game_time=game,
        locked_at=LOCK,locked_k_line=3.5,locked_odds=128,locked_book='fanduel',locked_verdict='LEAN',
        source_artifact_path='synthetic://official-artifact',source_artifact_sha256=artifact['byte_sha256'])
    market=dict(snapshots=[receipt(s, name=s['id'],event_at=s['observed_at']) for s in snapshots],
        current_lines=receipt(lines,name='current-lines'),heartbeats=receipt([],name='heartbeats'),
        windows=receipt(windows,DATE+'T19:55:00+00:00',name='window'),
        read=receipt(dict(complete=True,reason_codes=[],window_start=START,window_end=LOCK,
                          expected_count=len(snapshots),returned_count=len(snapshots)),LOCK,name='read-completion'))
    ident={k:lock[k] for k in ('slate_date','normalized_pitcher','side','game_time')}
    ident.update(game_identity=candidate['game_identity'],lock_id=lock['id'])
    envelope=dict(schema=v.SCHEMA,evidence_kind='synthetic',identity=ident,frozen=frozen,lock=lock,
        artifact_proof=artifact,market_proof=market,decision_time=copy.deepcopy(proof['normalized_inputs']),
        agreement=dict(status='known',label={'toward':'market_with_model','against':'market_against_model','mixed':'market_mixed','neutral':'market_no_signal'}[agreement]),
        preclose=dict(status='known',label=pre['label'],score=pre['score']),
        path_b={k:pitcher[k] for k in v.PATH_FIELDS},
        provenance=dict(completed_at=DATE+'T20:10:02+00:00',persisted_at=DATE+'T20:10:03+00:00',capture_run_id='synthetic-run'))
    envelope['path_b'].update(status='known',source_artifact_sha256=artifact['byte_sha256'])
    v.seal(envelope)
    quote={k:lock[k] for k in ('slate_date','normalized_pitcher','side','game_time','locked_at','locked_k_line','locked_odds','locked_book','locked_verdict')}
    def attachment(kind,data,at):
        return dict(kind=kind,envelope_sha256=envelope['content_sha256'],identity=ident,
                    receipt=receipt(data,at,name=kind))
    consumed=DATE+'T20:11:00+00:00'
    attachments=[attachment('consumption',dict(lock_id=lock['id'],consumed_at=consumed,**quote),consumed),
        attachment('seed',dict(quote,result=None,recovery_status='original'),DATE+'T20:12:00+00:00'),
        attachment('settlement',dict(quote,result='loss',pnl=-1,recovery_status='original'),DATE+'T23:00:00+00:00'),
        attachment('close',dict(quote,closing_line=3.5,closing_odds=128,closing_book='fanduel',closing_provider='therundown',clv_type='no_clv_edge',observed_at=DATE+'T20:39:00+00:00'),DATE+'T23:00:00+00:00')]
    manifest=v.reference_manifest()
    if activated:
        manifest['activation']=dict(activated_at='2026-09-05T00:00:00+00:00',first_unobserved_slate=DATE,
             capture_sink='synthetic://sink',review_ref='synthetic://review',implementation_commit='a'*40)
    envelope['manifest_sha256']=v.digest(manifest)
    v.seal(envelope)
    for a in attachments: a['envelope_sha256']=envelope['content_sha256']
    return dict(manifest=manifest,envelopes=[envelope],attachments=attachments,
                inventory=[dict(identity=ident,status='captured')],start_date=DATE,end_date=DATE)

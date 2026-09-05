"""Explicit synthetic source receipts for the offline capture prototype."""
import copy
from pathlib import Path
import runpy

from analytics.diagnostics import forward_pregame_evidence_validator as v

factory = runpy.run_path(str(Path(__file__).with_name('forward_evidence_factory.py')))


def source_bundle(**kwargs):
    packet = factory['build_case'](activated=False, **kwargs)
    envelope = copy.deepcopy(packet['envelopes'][0])
    read = v.decode_receipt(envelope['market_proof']['read'])
    read.update(page_size=1000, page_row_counts=[len(envelope['market_proof']['snapshots'])],
                provider_run_read_complete=True)
    envelope['market_proof']['read'] = factory['receipt'](read, factory['LOCK'], name='read-completion')
    capture = {k: copy.deepcopy(envelope[k]) for k in (
        'identity','artifact_proof','market_proof','decision_time','agreement','preclose','path_b','provenance')}
    capture.update(frozen_id=envelope['frozen']['id'], lock_id=envelope['lock']['id'])
    attachments = [{k: copy.deepcopy(a[k]) for k in ('identity','kind','receipt')}
                   for a in packet['attachments'] if a['kind'] in {'consumption','seed'}]
    seed = next(a for a in attachments if a['kind']=='seed')
    data = v.decode_receipt(seed['receipt'])
    data.update(source_run_id='synthetic-ordinary-run', source_event_type='ordinary_ungraded_lock_witness')
    seed['receipt'] = factory['receipt'](data, '2026-09-06T20:12:00+00:00', name='seed')
    return dict(schema='forward_capture_sources_v1', slate_date=factory['DATE'], evidence_kind='synthetic',
        manifest=packet['manifest'], source_scope=dict(complete=True, frozen_count=1, lock_count=1),
        frozen_rows=[envelope['frozen']], lock_rows=[envelope['lock']], captures=[capture], attachments=attachments)

"""Rebuild the captured packet in memory and verify the saved evidence; no writes."""
from pathlib import Path
import gzip
import hashlib
import json
import sys

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]
sys.path.insert(0, str(ROOT))
from analytics.diagnostics.decision_time_research_adapter import build_packet, read_rows


def verify():
    packet_bytes = gzip.decompress((HERE/'run/packet.json.gz').read_bytes())
    saved = json.loads(packet_bytes)
    loaded = {}
    for name, spec in saved['source_files'].items():
        path = ROOT/spec['path']
        assert hashlib.sha256(path.read_bytes()).hexdigest() == spec['sha256'], name
        loaded[name] = read_rows(path, source=name)
    rebuilt = build_packet(gate_c_rows=loaded['gate_c'], lock_rows=loaded['lock'],
                           frozen_rows=loaded['frozen'], start_date=saved['start_date'], end_date=saved['end_date'])
    assert rebuilt == {k: v for k, v in saved.items() if k != 'source_files'}
    def key(row):
        return tuple(row['identity'][k] for k in ('slate_date', 'normalized_pitcher', 'side'))
    frozen = {key(r) for r in saved['records'] if r['selector_match'] is True}
    archive = {key(r) for r in saved['records'] if r['archive_selector_match'] is True}
    linked = [r for r in saved['records'] if r['selector_match'] is True and r['linkage_status'] == 'linked']
    assert len(frozen & archive) == 21
    assert len(linked) == 19
    assert all(r['pregame_evidence']['preclose'] is None for r in saved['records'])
    assert not any(r['formal_prospective_credit'] for r in saved['records'])
    return {'summary': saved['summary'], 'archive_frozen_overlap': len(frozen & archive),
            'frozen_only': sorted(frozen-archive), 'archive_only': sorted(archive-frozen),
            'linked_selector_dates': len({r['identity']['slate_date'] for r in linked}),
            'linked_selector_pitchers': len({r['identity']['normalized_pitcher'] for r in linked}),
            'frozen_selector_book_conflicts': [r['identity'] for r in saved['records'] if r['selector_match'] is True and 'archive_lock_book_mismatch' in r['exclusion_reasons']],
            'source_capture': json.loads(gzip.decompress((HERE/'frozen-source.json.gz').read_bytes()))['captured_at'],
            'packet_uncompressed_sha256': hashlib.sha256(packet_bytes).hexdigest(),
            'adapter_sha256': hashlib.sha256((ROOT/'analytics/diagnostics/decision_time_research_adapter.py').read_bytes()).hexdigest()}


if __name__ == '__main__':
    print(json.dumps(verify(), indent=2, sort_keys=True))

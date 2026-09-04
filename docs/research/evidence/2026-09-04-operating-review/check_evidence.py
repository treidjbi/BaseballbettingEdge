"""Read-only reproduction of the September 4 operating review snapshot."""
import json
from pathlib import Path

root = Path(__file__).resolve().parent
evidence = json.loads((root / 'read-only-evidence.json').read_text())
rows = evidence['alt_rows']
keys = set()
for row in rows:
    key = (row['slate_date'], row['pitcher'], row['side'])
    assert key not in keys
    keys.add(key)
    assert row['lock_valid'] and row['prestart_valid']
    assert row['selector_fingerprint'] == '23bacff0fa923685ae52c5a9cfbadfb9f5902fb64d91759cfe9b4b1169a221c4'
    assert len(row['history_matches']) == 1
    h = row['history_matches'][0]
    from datetime import datetime
    game_time = row['game_time'] + ':00' if row['game_time'].endswith('+00') else row['game_time']
    assert datetime.fromisoformat(h['game_time'].replace('Z', '+00:00')) == datetime.fromisoformat(game_time)
    assert float(h['locked_k_line'] or h['k_line']) == float(row['model_k_line'])
    assert h['locked_odds'] == row['official_odds']
    assert h['result'] in ('win', 'loss', 'void')
    if h['result'] != 'void':
        ks, line = float(h['actual_ks']), float(row['model_k_line'])
        win = ks > line if row['side'] == 'over' else ks < line
        assert ks != line and win == (h['result'] == 'win')
    row['grade'] = h['result']
    odds = row['official_odds']
    row['pnl'] = (odds / 100 if odds > 0 else 100 / -odds) if h['result'] == 'win' else (-1 if h['result'] == 'loss' else 0)

def stats(rs):
    graded = [r for r in rs if r['grade'] in ('win', 'loss')]
    pnl = sum(r['pnl'] for r in rs)
    return dict(selected=len(rs), wins=sum(r['grade']=='win' for r in rs), losses=sum(r['grade']=='loss' for r in rs), voids=sum(r['grade']=='void' for r in rs), pnl=round(pnl, 6), roi_percent=round(100*pnl/len(graded), 3) if graded else None, slates=len({r['slate_date'] for r in rs}))

days = sorted({r['slate_date'] for r in rows})
summary = {'total': stats(rows)}
for field in ('lane', 'side', 'official_verdict', 'official_book', 'provider_posture', 'model_k_line'):
    summary[field] = {v: stats([r for r in rows if r[field]==v]) for v in sorted({r[field] for r in rows})}
summary['price'] = {v: stats([r for r in rows if (r['official_odds']>0)==(v=='plus')]) for v in ('plus','minus')}
summary['latest_14_selected_slates'] = stats([r for r in rows if r['slate_date'] in days[-14:]])
loso = [sum(r['pnl'] for r in rows if r['slate_date']!=d) for d in days]
summary['leave_one_slate_out'] = dict(min=round(min(loso),6), max=round(max(loso),6))
mainline = sum(r['pnl'] * (2 if r['official_verdict']=='FIRE 2u' else 1 if r['official_verdict']=='FIRE 1u' else 0) for r in rows)
summary['paired_same_rows_only'] = dict(mainline_displayed_fire_pnl=round(mainline,6), alternative_flat_pnl=summary['total']['pnl'], delta=round(sum(r['pnl'] for r in rows)-mainline,6), warning='Different risk exposure; this is not the full mainline portfolio or a causal effect.')
summary['integrity'] = dict(unique_keys=len(keys), matched_history=len(rows), exact_line_odds_time=len(rows), consumed_locks=len(rows), invalid=0)
print(json.dumps(summary, indent=2))

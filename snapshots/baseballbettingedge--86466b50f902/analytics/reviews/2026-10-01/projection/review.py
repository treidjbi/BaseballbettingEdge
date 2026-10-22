"""Offline descriptive review. Run from repository root; stdlib only; no network."""
import json, csv, hashlib, math, statistics, collections
from pathlib import Path
from datetime import date, timedelta
ROOT=Path(__file__).resolve().parents[4]
OUT=Path(__file__).resolve().parent
SRC=ROOT/'data/research/gate_c/pitcher_k_outcome_dataset.jsonl'
rows=[json.loads(x) for x in SRC.read_text().splitlines()]
assert hashlib.sha256(SRC.read_bytes()).hexdigest()==json.loads((SRC.parent/'pitcher_k_outcome_dataset_manifest.json').read_text())['jsonl_sha256']
groups=collections.defaultdict(list)
for r in rows: groups[(r['slate_date'],r['normalized_pitcher'])].append(r)
for g in groups.values():
 assert len(g)==2 and {r['side'] for r in g}=={'over','under'}
 for k in ['projected_ks','actual_ks','k_line','game_time']: assert len({r[k] for r in g})==1
starts=[next(r for r in g if r['side']=='over') for g in groups.values()]
def avg(x): return statistics.mean(x) if x else None
def table(name,data):
 if not data:return
 with (OUT/(name+'.csv')).open('w',newline='') as f:
  w=csv.DictWriter(f,fieldnames=list(data[0]));w.writeheader();w.writerows(data)
comparison=[]
for key,g in sorted(groups.items()):
 over=next(r for r in g if r['side']=='over');under=next(r for r in g if r['side']=='under')
 assert over['team']==under['team'] and over['opp_team']==under['opp_team']
 comparison.append(dict(date=over['slate_date'],pitcher=over['pitcher'],team=over['team'],opponent=over['opp_team'],projected_ks=over['projected_ks'],line=over['k_line'],actual_ks=over['actual_ks'],model_error=over['projected_ks']-over['actual_ks'],line_error=over['k_line']-over['actual_ks'],over_probability=over['model_win_prob'],over_odds=over['american_odds'],under_odds=under['american_odds']))
table('pitcher_game_comparison',comparison)
(OUT/'pitcher_game_comparison.json').write_text(json.dumps(comparison,separators=(',',':'))+'\n')
def week(r):
 d=date.fromisoformat(r['slate_date']);return str(d-timedelta(days=d.weekday()))
def sliced(data,func,stat):
 d=collections.defaultdict(list)
 for r in data:d[str(func(r))].append(r)
 return [dict(slice=k,**stat(v)) for k,v in sorted(d.items())]
def proj(rs):
 out={'n':len(rs),'actual_mean':avg([r['actual_ks'] for r in rs])}
 for name,fn in [('model',lambda r:r['projected_ks']),('line',lambda r:r['k_line']),('shrink15',lambda r:r['projected_ks']*.85+r['k_line']*.15),('shrink25',lambda r:r['projected_ks']*.75+r['k_line']*.25),('shrink35',lambda r:r['projected_ks']*.65+r['k_line']*.35)]:
  e=[fn(r)-r['actual_ks'] for r in rs]
  out.update({name+'_mean':avg([fn(r) for r in rs]),name+'_bias':avg(e),name+'_mae':avg([abs(x) for x in e]),name+'_rmse':math.sqrt(avg([x*x for x in e]))})
 return out
for name,fn in [('overall',lambda r:'all'),('monthly',lambda r:r['slate_date'][:7]),('weekly',week),('pitcher_team',lambda r:r['team']),('opponent',lambda r:r['opp_team']),('line',lambda r:r['k_line'])]:table('projection_'+name,sliced(starts,fn,proj))
def cal(rs):
 out={'n':len(rs),'win_rate':avg([r['result']=='win' for r in rs])}
 for k in ['model_win_prob','no_vig_side_probability']:
  use=[r for r in rs if isinstance(r.get(k),(int,float))]
  out[k+'_n']=len(use);out[k+'_mean']=avg([r[k] for r in use]);out[k+'_brier']=avg([(r[k]-(r['result']=='win'))**2 for r in use])
 return out
tracked=[r for r in rows if r['is_tracked_pick']]
for name,fn in [('side',lambda r:r['side']),('monthly',lambda r:r['slate_date'][:7]),('probability',lambda r:f"{math.floor(r['model_win_prob']*10)/10:.1f}"),('line',lambda r:r['k_line'])]:table('calibration_tracked_'+name,sliced(tracked,fn,cal))
table('calibration_tracked_exact_line_side',sliced([r for r in tracked if r['bet_time_line']==r['k_line']],lambda r:r['side'],cal))
assert not any(r['actual_ks']==r['k_line'] for r in rows)
assert all((r['result']=='win')==((r['actual_ks']>r['k_line']) if r['side']=='over' else (r['actual_ks']<r['k_line'])) for r in rows)
assert all(abs(sum(r['model_win_prob'] for r in g)-1)<0.00011 for g in groups.values())
table('calibration_all_over' ,sliced(starts,lambda r:'all_over',cal))
def movement(rs):
 # Gate C research side rows, NOT published-PnL/account accounting.
 pnl=[r['pick_history_pnl'] for r in rs if isinstance(r.get('pick_history_pnl'),(int,float))]
 return dict(n=len(rs),wins=sum(r['result']=='win' for r in rs),win_rate=avg([r['result']=='win' for r in rs]),history_pnl_rows=len(pnl),history_pnl_sum=sum(pnl))
for name,fn in [('price_movement',lambda r:r['side_price_movement']),('clv_label',lambda r:r['clv_type']),('monthly_price_movement',lambda r:r['slate_date'][:7]+' '+str(r['side_price_movement'])),('clv_same_book',lambda r:('same_book' if r['bet_time_book']==r['bookmaker_key'] else 'cross_book')+' '+r['clv_type'])]:table(name,sliced(tracked,fn,movement))
meta=[r for r in starts if isinstance(r.get('projection_challenger'),dict)]
paired=[r for r in meta if all(isinstance(r['projection_challenger'].get(k),(int,float)) for k in ['current_lambda','would_lambda'])]
pair={k:avg([abs(r['projection_challenger'][k]-r['actual_ks']) for r in paired]) for k in ['current_lambda','would_lambda']}
summary={'source_sha256':hashlib.sha256(SRC.read_bytes()).hexdigest(),'side_rows':len(rows),'pitcher_dates':len(starts),'tracked_research_side_rows':len(tracked),'dates':[min(r['slate_date'] for r in rows),max(r['slate_date'] for r in rows)],'overall_projection':proj(starts),'challenger_paired_n':len(paired),'challenger_mae':pair,'non_null_fields':{k:sum(r.get(k)!=None for r in rows) for k in ['line_movement','market_agreement_label','side_price_movement','bet_time_at','opening_odds','actual_ks','projected_ks']},'tracked_cross_book':sum(r['bet_time_book']!=r['bookmaker_key'] for r in tracked)}
(OUT/'summary.json').write_text(json.dumps(summary,indent=2)+'\n')
print(json.dumps(summary,indent=2))

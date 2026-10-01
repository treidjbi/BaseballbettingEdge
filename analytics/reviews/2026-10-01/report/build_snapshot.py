import json,csv,pathlib
root=pathlib.Path.cwd(); app=pathlib.Path('/Users/tyler/Documents/Codex/BBE-2026-Season-Review'); base=root/'analytics/reviews/2026-10-01'
d=json.loads((app/'src/data.json').read_text()); q=d['queries']
r=json.loads((base/'results/results_summary.json').read_text())
for scope,tiers in r['scopes'].items():
 for tier,cuts in tiers.items():
  for cut,rows in cuts.items():
   if not isinstance(rows,list): continue
   q[f'{scope}_{tier}_{cut}']={'rows':rows,'source':{'label':'Preserved published history, October 1 15:08 UTC','files':['analytics/reviews/2026-10-01/sources/published_history.json'],'caveats':['Published verdict; flat 1u risk per settled pick. Not actual account PnL. Later publication reconciles headline totals but differs from original freeze hash. Clean regime begins April 28. Full-season team attribution missing for 655 settled picks.']}}
for p in (base/'projection').glob('*.csv'):
 rows=list(csv.DictReader(p.open()))
 for row in rows:
  for k,v in row.items():
   try: row[k]=float(v) if v else None
   except ValueError: pass
 q[p.stem]={'rows':rows,'source':{'label':'Frozen Gate C outcome dataset; offline October 1 review','files':['data/research/gate_c/pitcher_k_outcome_dataset.jsonl'],'caveats':['Final artifact context, not assured original decision-time forecast. Projection has 2744 paired pitcher-dates. Tracked research sides differ from published picks. Movement is retrospective opening/current price evidence, not executable CLV.']}}
d['buildStatus']='complete';(app/'src/data.json').write_text(json.dumps(d))

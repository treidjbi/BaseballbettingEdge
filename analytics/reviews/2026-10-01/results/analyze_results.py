"""Offline, stdlib-only published-history analysis. No network or grading calls.
Run from repository root: python3 analytics/reviews/2026-10-01/results/analyze_results.py
"""
import collections, datetime, hashlib, json, math, pathlib, statistics
ROOT=pathlib.Path(__file__).resolve().parents[4]
OUT=pathlib.Path(__file__).resolve().parent
SOURCE=OUT.parent/'sources/published_history.json'

def wilson(w,n):
    if not n:return [None,None]
    z=1.959963984540054;p=w/n;d=1+z*z/n;c=(p+z*z/(2*n))/d;h=z*math.sqrt(p*(1-p)/n+z*z/(4*n*n))/d
    return [100*(c-h),100*(c+h)]
def calc(rows):
    counts=collections.Counter(r.get('result') for r in rows);settled=[r for r in rows if r.get('result') in ('win','loss')]
    pnl=sum(float(r.get('pnl') or 0) for r in rows);n=len(settled);w=counts['win']
    profits=[float(r.get('pnl') or 0) for r in settled]
    return dict(rows=len(rows),wins=w,losses=counts['loss'],voids=counts['void'],pushes=counts['push'],other_results={str(k):v for k,v in counts.items() if k not in ('win','loss','void','push')},settled=n,pnl_units=pnl,flat_risk_units=n,roi_pct=100*pnl/n if n else None,win_pct=100*w/n if n else None,win_pct_wilson95=wilson(w,n),small_sample=n<100)
def verdict(r):return r.get('verdict') or 'UNKNOWN' # Freeze uses published verdict, not locked_verdict.
def group(rows, key):
    groups=collections.defaultdict(list)
    for r in rows:groups[key(r)].append(r)
    return [dict(group=k,**calc(v)) for k,v in sorted(groups.items())]
def norm(x):
    import unicodedata
    return ''.join(c for c in unicodedata.normalize('NFKD',x.lower()) if not unicodedata.combining(c))
def main():
    raw=SOURCE.read_bytes();history=json.loads(raw)
    if isinstance(history,dict):history=history.get('payload',history.get('data',history.get('picks_history')))
    assert isinstance(history,list)
    research_path=ROOT/'data/research/gate_c/pitcher_k_outcome_dataset.jsonl'
    research=[json.loads(s) for s in research_path.read_text().splitlines()]
    bykey=collections.defaultdict(list)
    for r in research:bykey[(r['slate_date'],norm(r['pitcher']),r['side'])].append(r)
    mismatches=[];matches=0;missing=0
    for r in history:
        r['_verdict']=verdict(r);r['_tier']='FIRE' if r['_verdict'].startswith('FIRE') else ('LEAN' if r['_verdict'].startswith('LEAN') else 'OTHER')
        # History identity owns PnL. Research supplies team only when unambiguous.
        rs=bykey.get((r['date'],norm(r['pitcher']),r['side']),[])
        for field in ('team','opp_team'):
            values={x.get(field) for x in rs if x.get(field)}
            r['_'+field]=next(iter(values)) if len(values)==1 else 'UNKNOWN'
        if '2026-04-28'<=r['date']<='2026-09-27' and r.get('result') in ('win','loss'):
            if rs:matches+=1
            else:missing+=1
        if r.get('result') in ('win','loss'):
            odds=r.get('locked_odds') if r.get('locked_odds') is not None else r.get('odds')
            expected=(-1 if r['result']=='loss' else (odds/100 if odds>0 else 100/abs(odds))) if odds else None
            if expected is None or abs(expected-float(r.get('pnl') or 0))>1e-6:mismatches.append({k:r.get(k) for k in ('date','pitcher','result','odds','locked_odds','pnl')})
    report={'source':str(SOURCE.relative_to(ROOT)),'source_sha256':hashlib.sha256(raw).hexdigest(),'history_rows':len(history),'research_sha256':hashlib.sha256(research_path.read_bytes()).hexdigest(),'history_date_range':[min(r['date'] for r in history),max(r['date'] for r in history)],'settled_clean_research_identity_matches':matches,'settled_clean_research_identity_missing':missing,'pnl_formula_mismatch_count':len(mismatches),'pnl_formula_mismatches':mismatches,'scopes':{},'verdict_definition':'published verdict; matches October 1 freeze', 'locked_verdict_sensitivity':calc([r for r in history if '2026-04-28'<=r['date']<='2026-09-27' and (r.get('locked_verdict') or r.get('verdict') or '').startswith('FIRE')]), 'tier_changes':[{k:r.get(k) for k in ('date','pitcher','verdict','locked_verdict','result','pnl')} for r in history if '2026-04-28'<=r['date']<='2026-09-27' and (r.get('verdict') or '').startswith('FIRE') != (r.get('locked_verdict') or r.get('verdict') or '').startswith('FIRE')]}
    for name,start in [('all_published','0000-00-00'),('clean_regime','2026-04-28')]:
        base=[r for r in history if start<=r['date']<='2026-09-27' and r['_tier'] in ('FIRE','LEAN')]
        scope={}
        for tier in ['ALL','FIRE','LEAN']:
            rows=[r for r in base if tier=='ALL' or r['_tier']==tier]
            scope[tier]={'overall':calc(rows),'month':group(rows,lambda r:r['date'][:7]),'week':group(rows,lambda r:datetime.date.fromisoformat(r['date']).strftime('%G-W%V')),'pitcher_team':group(rows,lambda r:r['_team']),'opponent_team':group(rows,lambda r:r['_opp_team']),'side':group(rows,lambda r:r['side']),'month_side':group(rows,lambda r:r['date'][:7]+' '+r['side'])}
        report['scopes'][name]=scope
    # Every partition must reconcile to its parent population.
    for tiers in report['scopes'].values():
        for cuts in tiers.values():
            for cut,parts in cuts.items():
                if cut=='overall':continue
                for metric in ('rows','settled','wins','losses','voids','pnl_units'):
                    assert abs(sum(x[metric] for x in parts)-cuts['overall'][metric])<1e-7,(cut,metric)
    assert len(history)==4102
    clean=report['scopes']['clean_regime']
    assert clean['ALL']['overall']['settled']==2777
    assert abs(clean['FIRE']['overall']['pnl_units']-(-45.0261711146485))<1e-7
    assert abs(clean['LEAN']['overall']['pnl_units']-(-140.96436576811614))<1e-7
    (OUT/'results_summary.json').write_text(json.dumps(report,indent=2)+'\n')
    import csv
    for scope,tiers in report['scopes'].items():
        for tier,cuts in tiers.items():
            for cut,rows in cuts.items():
                if cut=='overall':continue
                with (OUT/f'{scope}_{tier.lower()}_{cut}.csv').open('w') as f:
                    writer=csv.DictWriter(f,fieldnames=list(rows[0]));writer.writeheader();writer.writerows(rows)
    print(json.dumps({k:v for k,v in report.items() if k!='scopes' and k!='pnl_formula_mismatches'},indent=2))
    print(json.dumps(report['scopes']['clean_regime']['FIRE']['month'],indent=2))
if __name__=='__main__':main()

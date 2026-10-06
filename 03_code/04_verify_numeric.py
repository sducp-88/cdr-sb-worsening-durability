"""Independent primary-count reconstruction plus known-value and aggregate QA."""
from pathlib import Path
import json,pandas as pd,numpy as np,importlib.util
from repro_paths import nacc_file, results_dir, output_dir, baseline_results_file
R=Path(__file__).resolve().parents[1];O=results_dir();out=[]
def ck(name,yes,detail=None):out.append({'check':name,'pass':bool(yes),'detail':detail})
res=json.loads((O/'analysis_results_v2.json').read_text(encoding='utf8'))
n=pd.read_csv(nacc_file(),usecols=['NACCID','VISITDATE','NACCAGE','NACCUDSD','CDRGLOB','CDRSUM','MEMORY','ORIENT','JUDGMENT','COMMUN','HOMEHOBB','PERSCARE'],low_memory=False)
n['date']=pd.to_datetime(n.VISITDATE,format='mixed')
counts={'baseline':0,'index':0,'crossers':0,'observed':0,'persistent':0,'nonpersistent':0}
for pid,g in n.groupby('NACCID',sort=False):
 g=g.sort_values('date')
 if g.date.iloc[0]<pd.Timestamp('2017-01-01'):continue
 values=g[['MEMORY','ORIENT','JUDGMENT','COMMUN','HOMEHOBB','PERSCARE']].to_numpy()
 good=(np.isin(values[:,:5],[0,.5,1,2,3]).all(1)&np.isin(values[:,5],[0,1,2,3])&np.isclose(values.sum(1),g.CDRSUM.to_numpy())&g.CDRSUM.between(0,18).to_numpy())
 h=g[good].copy()
 if h.empty:continue
 eligible=(h.NACCAGE.ge(50)&(h.date<=pd.Timestamp('2023-12-31'))&((h.NACCUDSD.eq(3)&h.CDRGLOB.isin([0,.5]))|(h.NACCUDSD.eq(4)&h.CDRGLOB.eq(1))))
 positions=np.where(eligible)[0]
 if len(positions)==0:continue
 b=h.iloc[positions[0]];counts['baseline']+=1
 days=(h.date-b.date).dt.days.to_numpy()
 iw=np.where((days>=.75*365.25)&(days<=1.25*365.25))[0]
 if len(iw)==0:continue
 ii=iw[np.argmin(np.abs(days[iw]-365.25))];counts['index']+=1
 threshold={3:1,4:2}[int(b.NACCUDSD)]
 if float(h.iloc[ii].CDRSUM-b.CDRSUM)<threshold:continue
 counts['crossers']+=1
 cw=np.where((days>=1.75*365.25)&(days<=2.25*365.25))[0]
 if len(cw)==0:continue
 ci=cw[np.argmin(np.abs(days[cw]-730.5))];counts['observed']+=1
 pers=float(h.iloc[ci].CDRSUM-b.CDRSUM)>=threshold
 counts['persistent' if pers else 'nonpersistent']+=1
target=res['disposition']['NACC_post2016']['All']
for k,v in counts.items():ck('independent_NACC_'+k,v==target[k],{'independent':v,'pipeline':target[k]})
for c,stages in res['disposition'].items():
 for st,d in stages.items():
  ck(f'{c}/{st}/disposition_sum',d['crossers']==d['persistent']+d['nonpersistent']+d['known_death_no_confirmation']+d['other_no_confirmation'])
  ck(f'{c}/{st}/observed_sum',d['observed']==d['persistent']+d['nonpersistent'])
  p=d['nonpersistence_observed']
  ck(f'{c}/{st}/denominator',p['n']==d['observed'])
  if p['n']:ck(f'{c}/{st}/ci_contains_point',p['lo']<=p['risk']<=p['hi'])
 ck(c+'/stage_partition',stages['All']['crossers']==stages['MCI']['crossers']+stages['Mild dementia']['crossers'])
# Golden FAQ mapping checks against actual official coding, not raw-code equality.
raw=np.array([0,1,2,3,4,5,-1,np.nan])
total=pd.Series(raw).map({0:0,1:0,2:1,3:1,4:2,5:3}).to_numpy()
performed=pd.Series(raw).map({0:0,3:1,4:2,5:3}).to_numpy()
ck('ADNI_six_code_total_mapping',np.allclose(total[:6],[0,0,1,1,2,3]))
ck('ADNI_never_did_not_observed_independence',np.isnan(performed[1:3]).all())
ck('ADNI_assistance_codes',np.allclose(performed[4:6],[2,3]))
ck('unknown_codes_stay_missing',np.isnan(total[6:]).all())
baseline=baseline_results_file()
if baseline is not None:
 a=json.loads(baseline.read_text(encoding='utf8'))
 ck('implementation_fix_did_not_change_primary',a['disposition']==res['disposition'])
 ck('implementation_fix_did_not_change_corroboration',a['corroboration']==res['corroboration'])
ck('primary_adjusted_model_not_silently_relaxed',res['models']['NACC_post2016']['status'].startswith('not_fitted'))
report={'baseline_comparison_included':baseline is not None,'checks':out,'passed':sum(x['pass'] for x in out),'total':len(out),'independent_primary_counts':counts,'scope':'Separate raw-data NACC reconstruction; ADNI aggregate/coding checks; not independent human review or full independent ADNI replication'}
(output_dir()/'independent_numeric_QA.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf8')
print(json.dumps({k:v for k,v in report.items() if k!='checks'},ensure_ascii=False,indent=2))
assert all(x['pass'] for x in out)


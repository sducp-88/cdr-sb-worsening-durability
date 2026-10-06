"""Build harmonized cohorts in memory; only aggregate results are written.
See README.md for the recorded environment and explicit local input configuration. No raw/derived participant rows exported.
"""
from pathlib import Path
import pandas as pd, numpy as np, json, hashlib, sys, platform
from datetime import datetime
from scipy.stats import norm
from statsmodels.stats.proportion import proportion_confint
import statsmodels.api as sm
from sklearn.linear_model import LogisticRegression
from sklearn.preprocessing import StandardScaler
from sklearn.pipeline import make_pipeline
from repro_paths import nacc_file, adni_root, output_dir, protocol_sha256
ROOT=Path(__file__).resolve().parents[1]; OUT=output_dir()
N=nacc_file(); A=adni_root()
F=['BILLS','TAXES','SHOPPING','GAMES','STOVE','MEALPREP','EVENTS','PAYATTN','REMDATES','TRAVEL']
AF=['FAQFINAN','FAQFORM','FAQSHOP','FAQGAME','FAQBEVG','FAQMEAL','FAQEVENT','FAQTV','FAQREM','FAQTRAVL']
CB=['memory','orient','judgment','community','home','care']
N_CB=['MEMORY','ORIENT','JUDGMENT','COMMUN','HOMEHOBB','PERSCARE']
A_CB=['CDMEMORY','CDORIENT','CDJUDGE','CDCOMMUN','CDHOME','CDCARE']
QA={}; MANIFEST=[]; SEED=20260917
def save(name,obj):
    (OUT/name).write_text(json.dumps(obj,ensure_ascii=False,indent=2,default=lambda x: int(x) if isinstance(x,np.integer) else float(x) if isinstance(x,np.floating) else str(x)),encoding='utf8')
def source(p):
    h=hashlib.sha256()
    with open(p,'rb') as f:
        for b in iter(lambda:f.read(8*1024*1024),b''):h.update(b)
    MANIFEST.append({'path':str(p),'bytes':p.stat().st_size,'sha256':h.hexdigest()})
def read(rel):
    p=A/rel;source(p); return pd.read_csv(p,low_memory=False)
def dedup(d,keys,values,tag):
    du=d.duplicated(keys,keep=False)
    conflict=d[du].groupby(keys,dropna=False)[values].nunique(dropna=False).gt(1).any(axis=1)
    ck=conflict[conflict].reset_index()[keys]
    if len(ck):
        d=d.merge(ck.assign(_conflict=True),on=keys,how='left')
        d=d[d._conflict.isna()].drop(columns='_conflict')
    QA[tag]={'duplicate_rows':int(du.sum()),'conflicting_keys_excluded':len(ck)}
    return d.drop_duplicates(keys,keep='first')
def cdr_qc(d,tag):
    valid=d.cdr.between(0,18)&d.cdr.mul(2).mod(1).eq(0)
    boxvalid=d[CB[:5]].isin([0,.5,1,2,3]).all(axis=1)&d['care'].isin([0,1,2,3])
    sums=d[CB].sum(axis=1,min_count=6)
    mismatch=boxvalid&valid&~np.isclose(sums,d.cdr)
    QA[tag]={'rows':len(d),'invalid_cdr':int((~valid).sum()),'invalid_components':int((~boxvalid).sum()),'sum_mismatch':int(mismatch.sum()),'date_missing':int(d.date.isna().sum())}
    d=d[valid&boxvalid&~mismatch&d.date.notna()].copy()
    d['cog']=d[CB[:3]].sum(axis=1)
    return d
def load_nacc():
    print('Reading NACC and checking codes...',flush=True);source(N)
    wanted=['NACCID','NACCADC','NACCVNUM','VISITDATE','NACCAGE','NACCSEX','EDUC','NACCUDSD','CDRGLOB','CDRSUM','NACCMMSE','NACCMOCA','NACCDIED','NACCMOD','NACCYOD','NACCALZD','INSEX','INRELTO','INBIRMO','INBIRYR']+F+N_CB
    d=pd.read_csv(N,usecols=lambda c:c in wanted,low_memory=False)
    d=d.rename(columns=dict(zip(N_CB,CB))|{'NACCID':'id','NACCADC':'site','NACCAGE':'age','NACCSEX':'sex','EDUC':'educ','CDRSUM':'cdr','CDRGLOB':'global','NACCUDSD':'dx','NACCMMSE':'mmse','NACCMOCA':'moca'})
    d['date']=pd.to_datetime(d.VISITDATE,format='mixed',errors='coerce')
    d['first_date']=d.groupby('id').date.transform('min')
    d['first_visit']=d.date.eq(d.first_date)
    d=dedup(d,['id','date'],['cdr','global','dx']+CB,'nacc_duplicates')
    d=cdr_qc(d,'nacc_cdr')
    for j,f in enumerate(F):
        d[f'q{j}']=pd.to_numeric(d[f],errors='coerce').where(d[f].isin([0,1,2,3]))
        d[f'p{j}']=d[f'q{j}']
    d['faq']=d[[f'q{j}' for j in range(10)]].sum(axis=1,min_count=10)
    d['faq_n']=d[[f'q{j}' for j in range(10)]].notna().sum(axis=1)
    d['mmse']=d.mmse.where(d.mmse.between(0,30));d['moca']=d.moca.where(d.moca.between(0,30))
    d['educ']=d.educ.where(d.educ.between(0,36));d['sex']=d.sex.where(d.sex.isin([1,2]))
    d['stage']=np.where(d.dx.eq(3)&d['global'].isin([0,.5]),'MCI',np.where(d.dx.eq(4)&d['global'].eq(1),'Mild dementia','Other'))
    d['known_ad']=d.NACCALZD.eq(1)
    yr=d.NACCYOD.where(d.NACCYOD.between(1900,2030));mo=d.NACCMOD.where(d.NACCMOD.between(1,12))
    d['death_end']=pd.to_datetime(pd.DataFrame({'year':yr,'month':mo,'day':1}),errors='coerce')+pd.offsets.MonthEnd(0)
    d.loc[~d.NACCDIED.eq(1),'death_end']=pd.NaT
    QA['nacc_death_before_visit']=int((d.death_end<d.date).sum())
    # Impossible death chronology is not silently corrected.
    d.loc[d.death_end<d.date,'death_end']=pd.NaT
    return d
def nearest(left,right,cols,tag,tol=30):
    l=left.reset_index(drop=True).copy();l['_rowkey']=np.arange(len(l))
    r=right[['id','date']+cols].dropna(subset=['id','date']).copy()
    r=r.rename(columns={'date':'match_date'})
    merged=pd.merge_asof(l.sort_values('date'),r.sort_values('match_date'),left_on='date',right_on='match_date',by='id',direction='nearest',tolerance=pd.Timedelta(days=tol))
    QA[tag]={'left_rows':len(l),'matched':int(merged.match_date.notna().sum()),'max_abs_gap_days':float((merged.date-merged.match_date).dt.days.abs().max())}
    return merged.drop(columns=['match_date','_rowkey']).sort_values(['id','date'])
def load_adni():
    print('Reading ADNI and harmonizing six-code FAQ...',flush=True)
    c=read('03_clinical_outcomes/neuropsychological/CDR_30Aug2026.csv')
    c=c[~c.HAS_QC_ERROR.eq(1)].rename(columns=dict(zip(A_CB,CB))|{'RID':'id','SITEID':'site','CDRSB':'cdr','CDGLOBAL':'global'})
    c['date']=pd.to_datetime(c.VISDATE,format='mixed',errors='coerce')
    c['first_date']=c.groupby('id').date.transform('min');c['first_visit']=c.date.eq(c.first_date)
    c=dedup(c,['id','date'],['cdr','global']+CB,'adni_cdr_duplicates')
    c=cdr_qc(c,'adni_cdr')
    c=c[['id','site','date','first_date','first_visit','cdr','global','cog','PHASE']+CB]
    dx=read('01_core_cohort/diagnosis/DXSUM_30Aug2026.csv').rename(columns={'RID':'id','DIAGNOSIS':'dx'})
    dx=dx[~dx.HAS_QC_ERROR.eq(1)]
    dx['date']=pd.to_datetime(dx.EXAMDATE,format='mixed',errors='coerce')
    dx=dedup(dx,['id','date'],['dx'],'adni_dx_duplicates')
    c=nearest(c,dx,['dx'],'adni_dx_alignment')
    f=read('03_clinical_outcomes/neuropsychological/FAQ_30Aug2026.csv').rename(columns={'RID':'id'})
    f=f[~f.HAS_QC_ERROR.eq(1)]
    f['date']=pd.to_datetime(f.VISDATE,format='mixed',errors='coerce')
    f=dedup(f,['id','date'],AF,'adni_faq_duplicates')
    for j,col in enumerate(AF):
        f[f'q{j}']=f[col].map({0:0,1:0,2:1,3:1,4:2,5:3})
        f[f'p{j}']=f[col].map({0:0,3:1,4:2,5:3}) # exclude "never did"
    qs=[f'q{j}' for j in range(10)];ps=[f'p{j}' for j in range(10)]
    f['faq']=f[qs].sum(axis=1,min_count=10);f['faq_n']=f[qs].notna().sum(axis=1)
    QA['adni_faq_total']={'valid_recomputed':int(f.faq.notna().sum()),'matches_official':int(np.isclose(f.faq,f.FAQTOTAL,equal_nan=False).sum()),'both_valid_disagree':int((f.faq.notna()&f.FAQTOTAL.between(0,30)&~np.isclose(f.faq,f.FAQTOTAL)).sum())}
    c=nearest(c,f,qs+ps+['faq','faq_n'],'adni_faq_alignment')
    demo=read('01_core_cohort/demographics/PTDEMOG_30Aug2026.csv').rename(columns={'RID':'id','PTGENDER':'sex','PTEDUCAT':'educ'})
    demo=demo[~demo.HAS_QC_ERROR.eq(1)].copy()
    demo['dob']=pd.to_datetime(demo.PTDOB,format='%m/%Y',errors='coerce')+pd.Timedelta(days=14)
    demo['date']=pd.to_datetime(demo.VISDATE,format='mixed',errors='coerce')
    # Demographic attributes are taken from the earliest dated valid report, no clinical future score is filled.
    demo=demo.sort_values(['id','date'])
    ds=demo.groupby('id')[['dob','sex','educ']].first().reset_index()
    c=c.merge(ds,on='id',how='left')
    c['age']=(c.date-c.dob).dt.days/365.25;c['educ']=c.educ.where(c.educ.between(0,36));c['sex']=c.sex.where(c.sex.isin([1,2]))
    c['stage']=np.where(c.dx.eq(2)&c['global'].isin([0,.5]),'MCI',np.where(c.dx.eq(3)&c['global'].eq(1),'Mild dementia','Other'))
    c['known_ad']=c.dx.eq(3)
    c['death_end']=pd.NaT
    p=read('04_imaging_derived/pet/UCBERKELEY_AMY_6MM_30Aug2026.csv').rename(columns={'RID':'id'})
    p['date']=pd.to_datetime(p.SCANDATE,format='mixed',errors='coerce')
    p=p[p.qc_flag.isin([1,2])&p.AMYLOID_STATUS.isin([0,1])]
    p=dedup(p,['id','date'],['AMYLOID_STATUS'],'adni_pet_duplicates')
    c=nearest(c,p,['AMYLOID_STATUS'],'adni_pet_alignment',tol=180)
    return c
def pick(g,target,lo,hi):
    w=g[g.date.between(lo,hi)]
    if w.empty:return None
    return w.assign(_gap=(w.date-target).abs()).sort_values(['_gap','date']).iloc[0]
def episode(d,label):
    records=[]; eligible=d[(d.age>=50)&d.stage.ne('Other')&(d.date<=pd.Timestamp('2023-12-31'))].sort_values(['id','date'])
    b=eligible.groupby('id',sort=False).head(1)
    gs={i:g.sort_values('date') for i,g in d.groupby('id',sort=False)}
    for _,r in b.iterrows():
        g=gs[r.id];bd=r.date
        i=pick(g,bd+pd.Timedelta(days=365.25),bd+pd.Timedelta(days=365.25*.75),bd+pd.Timedelta(days=365.25*1.25))
        c=pick(g,bd+pd.Timedelta(days=730.5),bd+pd.Timedelta(days=365.25*1.75),bd+pd.Timedelta(days=365.25*2.25))
        y3=pick(g,bd+pd.Timedelta(days=365.25*3),bd+pd.Timedelta(days=365.25*2.75),bd+pd.Timedelta(days=365.25*3.25))
        rec={'id':r.id,'site':r.site,'stage':r.stage,'age':r.age,'sex':r.sex,'educ':r.educ,'bdate':bd,'first_date':r.first_date,'entry_eligible':r.first_visit,
             'b_cdr':r.cdr,'b_cog':r['cog'],'b_faq':r.faq,'b_faq_n':r.faq_n,'threshold':1 if r.stage=='MCI' else 2,'known_ad':r.known_ad,'amyloid':r.get('AMYLOID_STATUS',np.nan),
             'index_observed':i is not None,'confirmation_observed':c is not None,'y3_observed':y3 is not None}
        for pref,row in [('i',i),('c',c),('y3',y3)]:
            for nm in ['cdr','cog','faq','date']:
                rec[pref+'_'+nm]=row[nm] if row is not None else (pd.NaT if nm=='date' else np.nan)
        rec['delta_i']=rec['i_cdr']-r.cdr;rec['delta_c']=rec['c_cdr']-r.cdr;rec['delta_y3']=rec['y3_cdr']-r.cdr
        rec['cross']=bool(i is not None and rec['delta_i']>=rec['threshold'])
        rec['persistent']=float(rec['delta_c']>=rec['threshold']) if c is not None else np.nan
        rec['new_dep']=np.nan;rec['valid_pairs']=0;rec['core_dep']=np.nan
        qb=np.array([r[f'p{j}'] for j in range(10)],dtype=float)
        rec['b_independent']=int(np.isin(qb,[0,1]).sum())
        if i is not None:
            qi=np.array([i[f'p{j}'] for j in range(10)],dtype=float)
            val=np.isfinite(qb)&np.isfinite(qi);ind=np.isin(qb,[0,1]);nd=ind&np.isin(qi,[2,3])
            rec['valid_pairs']=int(val.sum())
            if val.sum()>=8 and (ind&val).sum()>=1: rec['new_dep']=int(nd.any())
            core=[0,5,8,9]
            if val[core].all() and ind[core].any(): rec['core_dep']=int(nd[core].any())
            alt_window=g[g.date.between(i.date+pd.Timedelta(days=365.25*.75),i.date+pd.Timedelta(days=365.25*1.5))].sort_values('date')
            alt=alt_window.iloc[0] if len(alt_window) else None
            rec['alt_confirm']=alt is not None
            rec['alt_persist']=float(alt.cdr-r.cdr>=rec['threshold']) if alt is not None else np.nan
        if pd.notna(r.death_end) and i is not None:
            rec['death_no_confirm']=bool(c is None and i.date<=r.death_end<=bd+pd.Timedelta(days=365.25*2.25))
        else:rec['death_no_confirm']=False
        rec['stable_informant_proxy']=False
        if label=='NACC' and i is not None and c is not None:
            tr=[r,i,c]
            fields={'INSEX':[1,2],'INRELTO':list(range(1,10)),'INBIRMO':list(range(1,13)),'INBIRYR':list(range(1900,2027))}
            rec['stable_informant_proxy']=all(all(x.get(k,np.nan) in allowed for x in tr) and len(set(x[k] for x in tr))==1 for k,allowed in fields.items())
        # 36-month task-level new dependency relative to the same baseline.
        rec['new_dep_y3']=np.nan
        if y3 is not None:
            q3=np.array([y3[f'p{j}'] for j in range(10)],float);vv=np.isfinite(qb)&np.isfinite(q3)
            if vv.sum()>=8 and (np.isin(qb,[0,1])&vv).any():
                rec['new_dep_y3']=int((np.isin(qb,[0,1])&np.isin(q3,[2,3])).any())
        records.append(rec)
    return pd.DataFrame(records)
def prop(k,n):
    if not n:return {'n':0,'events':0,'risk':None,'lo':None,'hi':None}
    lo,hi=proportion_confint(k,n,alpha=.05,method='wilson')
    return {'n':int(n),'events':int(k),'risk':float(k/n),'lo':float(lo),'hi':float(hi)}
def disposition(g):
    x=g[g.cross];o=x[x.confirmation_observed];k=int(o.persistent.eq(0).sum());nd=int(x.death_no_confirm.sum());miss=len(x)-len(o)
    n=len(x)
    return {'baseline':len(g),'index':int(g.index_observed.sum()),'crossers':n,'observed':len(o),'persistent':int(o.persistent.eq(1).sum()),'nonpersistent':k,'known_death_no_confirmation':nd,'other_no_confirmation':miss-nd,
            'nonpersistence_observed':prop(k,len(o)),'bounds_all':[k/n,(k+miss)/n] if n else None,
            'bounds_without_known_deaths':[k/(n-nd),(k+miss-nd)/(n-nd)] if n>nd else None,
            'index_days_median':float((x.i_date-x.bdate).dt.days.median()) if n else None,
            'confirmation_after_index_days_median':float((o.c_date-o.i_date).dt.days.median()) if len(o) else None}
def difference(x,var='new_dep',target='persistent',reps=2000):
    z=x[x[var].isin([0,1])&x[target].isin([0,1])]
    a=z[z[var].eq(1)][target].to_numpy();b=z[z[var].eq(0)][target].to_numpy()
    if min(len(a),len(b))==0:return {'n':len(z),'status':'empty_group'}
    rng=np.random.default_rng(SEED)
    # Bernoulli bootstrap via binomial is exactly equivalent to resampling binary participant outcomes within groups.
    dif=rng.binomial(len(a),a.mean(),size=reps)/len(a)-rng.binomial(len(b),b.mean(),size=reps)/len(b)
    out={'n':len(z),'dependency_yes':prop(int(a.sum()),len(a)),'dependency_no':prop(int(b.sum()),len(b)),'risk_difference':float(a.mean()-b.mean()),'bootstrap_ci95':np.quantile(dif,[.025,.975]).tolist()}
    if z.site.nunique()>=20:
        agg=z.groupby(['site',var])[target].agg(['sum','size']).unstack(fill_value=0)
        sites=z.site.unique(); sums=[];nums=[]
        for site in sites:
            sg=z[z.site.eq(site)]
            sums.append([sg.loc[sg[var].eq(v),target].sum() for v in [0,1]])
            nums.append([sg[var].eq(v).sum() for v in [0,1]])
        sums=np.array(sums);nums=np.array(nums);rd=[]
        for k in range(reps):
            ix=rng.integers(0,len(sites),len(sites));den=nums[ix].sum(0)
            if min(den)>0: rates=sums[ix].sum(0)/den;rd.append(rates[1]-rates[0])
        out['center_bootstrap_ci95']=np.quantile(rd,[.025,.975]).tolist()
    return out
def adjusted(x):
    z=x[x.new_dep.isin([0,1])&x.persistent.isin([0,1])].copy()
    if min(z.persistent.value_counts().reindex([0,1],fill_value=0))<80:return {'status':'not_fitted_prespecified_less_than_80_in_an_outcome_class','n':len(z),'outcome_counts':z.persistent.value_counts().to_dict()}
    X=pd.DataFrame({'new_dep':z.new_dep,'mild_dementia':z.stage.eq('Mild dementia').astype(float),'age10':z.age/10,'female':z.sex.map({1:0,2:1}),'educ4':z.educ/4,'b_cdr':z.b_cdr,'delta_i':z.delta_i,'b_independent':z.b_independent})
    complete=X.notna().all(axis=1);X=sm.add_constant(X[complete]);y=z.loc[complete,'persistent'];sites=z.loc[complete,'site']
    if min(y.value_counts().reindex([0,1],fill_value=0))<80:return {'status':'not_fitted_after_covariate_missingness','n':len(y)}
    kw={'cov_type':'cluster','cov_kwds':{'groups':sites}} if sites.nunique()>=20 else {'cov_type':'HC1'}
    try:
        fit=sm.GLM(y,X,family=sm.families.Binomial()).fit(**kw)
        conf=fit.conf_int()
        return {'status':'fitted','n':len(y),'sites':sites.nunique(),'covariance':kw['cov_type'],'terms':{k:{'beta':float(v),'OR':float(np.exp(v)),'lo':float(np.exp(conf.loc[k,0])),'hi':float(np.exp(conf.loc[k,1]))} for k,v in fit.params.items()}}
    except Exception as e:return {'status':'failed','reason':str(e)}
def ipw(x):
    z=x[~x.death_no_confirm].copy()
    X=pd.DataFrame({'age':z.age,'female':z.sex.map({1:0,2:1}),'educ':z.educ,'stage':z.stage.eq('Mild dementia').astype(int),'b_cdr':z.b_cdr,'delta':z.delta_i,'interval':(z.i_date-z.bdate).dt.days,'year':z.i_date.dt.year,'faq':z.b_faq,'faq_available':z.b_faq.notna().astype(int),'new_dep':z.new_dep})
    X=X.assign(**{c+'_missing':X[c].isna().astype(int) for c in list(X.columns) if X[c].isna().any()})
    X=X.fillna(X.median()).fillna(0)
    obs=z.confirmation_observed.astype(int)
    if obs.nunique()<2:return {'status':'all_or_no_observed'}
    mod=make_pipeline(StandardScaler(),LogisticRegression(C=1,max_iter=3000,random_state=SEED))
    mod.fit(X,obs);p=mod.predict_proba(X)[:,1];p=np.clip(p,.05,.95)
    w=1/p[obs.eq(1)];y=z.loc[obs.eq(1),'persistent'].eq(0).astype(int).to_numpy()
    return {'status':'fitted','observed':len(y),'weighted_nonpersistence':float(np.average(y,weights=w)),'weight_quantiles':np.quantile(w,[0,.5,.9,.99,1]).tolist(),'effective_n':float(w.sum()**2/np.square(w).sum()),'conditional_on':'not known dead; MAR assumption, no weighting uncertainty interval'}
def summarize(groups):
    main={};corro=[];thresholds=[];sens={};models={};weights={};baseline=[]
    for name,g in groups.items():
        main[name]={}
        for st in ['All','MCI','Mild dementia']:
            sub=g if st=='All' else g[g.stage.eq(st)]
            main[name][st]=disposition(sub)
            x=sub[sub.cross&sub.confirmation_observed]
            cor=difference(x);corro.append({'cohort':name,'stage':st,**cor})
            for cutoff in [.5,1,2,3]:
                t=sub[sub.index_observed&(sub.delta_i>=cutoff)]
                o=t[t.confirmation_observed]
                thresholds.append({'cohort':name,'stage':st,'threshold':cutoff,'crossers':len(t),'observed':len(o),**prop(int(o.delta_c.lt(cutoff).sum()),len(o))})
        x=g[g.cross];o=x[x.confirmation_observed]
        models[name]=adjusted(o);weights[name]=ipw(x)
        sens[name]={}
        for nm,cond in {'all10_faq':o.valid_pairs.eq(10),'index_before_2021':o.i_date.lt('2021-01-01'),'clinical_AD':o.known_ad,'entry_eligible':o.entry_eligible,'stable_informant_proxy':o.stable_informant_proxy,'confirmation_before_2020':o.c_date.lt('2020-01-01'),'confirmation_2020plus':o.c_date.ge('2020-01-01')}.items():
            z=o[cond]
            sens[name][nm]={'nonpersistence':prop(int(z.persistent.eq(0).sum()),len(z)),'functional_corroboration':difference(z)}
        sens[name]['core_tasks']=difference(o,var='core_dep')
        alt=x[x.alt_confirm.fillna(False)]
        sens[name]['index_anchored_confirm']=prop(int(alt.alt_persist.eq(0).sum()),len(alt))
        # Observed 36-month outcomes by confirmed/nonpersistent status at 24 months.
        y3=o[o.y3_observed]
        sens[name]['year3_by_year2_status']={str(v):{'n':len(z),'still_above_original_threshold':prop(int(z.delta_y3.ge(z.threshold).sum()),len(z)),'new_dependency':prop(int(z.new_dep_y3.eq(1).sum()),int(z.new_dep_y3.notna().sum()))} for v,z in y3.groupby('persistent')}
        sens[name]['cognitive_boxes_by_new_dependency']={str(v):{'n':len(z),'mean_change':float((z.c_cog-z.b_cog).mean()),'sd_change':float((z.c_cog-z.b_cog).std())} for v,z in o[o.new_dep.isin([0,1])].groupby('new_dep')}
        for nm,z in [('index_crossers',x),('observed_confirmation',o),('no_confirmation',x[~x.confirmation_observed])]:
            baseline.append({'cohort':name,'group':nm,'n':len(z),'mci_n':int(z.stage.eq('MCI').sum()),'female_n':int(z.sex.eq(2).sum()),'age_mean':float(z.age.mean()),'age_sd':float(z.age.std()),'educ_mean':float(z.educ.mean()),'educ_missing':int(z.educ.isna().sum()),'b_cdr_median':float(z.b_cdr.median()),'b_cdr_q1':float(z.b_cdr.quantile(.25)),'b_cdr_q3':float(z.b_cdr.quantile(.75)),'delta_i_median':float(z.delta_i.median()),'faq_available_n':int(z.new_dep.notna().sum()),'new_dependency_n':int(z.new_dep.eq(1).sum()),'sites':int(z.site.nunique())})
    return {'disposition':main,'corroboration':corro,'thresholds':thresholds,'sensitivities':sens,'models':models,'ipw':weights,'characteristics':baseline}
def main():
    n=load_nacc();a=load_adni()
    print('Constructing one episode per participant...',flush=True)
    ne=episode(n,'NACC');ae=episode(a,'ADNI')
    groups={'NACC_post2016':ne[ne.first_date.ge('2017-01-01')].copy(),'NACC_legacy':ne[ne.first_date.lt('2017-01-01')].copy(),'ADNI':ae,'ADNI_amyloid_positive':ae[ae.amyloid.eq(1)].copy()}
    QA['episode_assertions']={}
    for name,g in groups.items():
        assert not g.id.duplicated().any()
        assert g.bdate.le(pd.Timestamp('2023-12-31')).all()
        assert (g.loc[g.index_observed,'i_date']>g.loc[g.index_observed,'bdate']).all()
        assert (g.loc[g.confirmation_observed&g.index_observed,'c_date']>g.loc[g.confirmation_observed&g.index_observed,'i_date']).all()
        QA['episode_assertions'][name]={'one_per_person':True,'temporal_order':True,'baseline_n':len(g)}
    save('harmonization_qa.json',QA);save('source_manifest.json',MANIFEST)
    print('All mandatory identity/time assertions passed. Estimating frozen outcomes...',flush=True)
    result=summarize(groups)
    result['analysis_time']=datetime.now().isoformat();result['protocol_sha256']=protocol_sha256()
    result['software']={'python':sys.version,'pandas':pd.__version__,'numpy':np.__version__,'platform':platform.platform()}
    result['script_sha256']=hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
    save('analysis_results_v2.json',result)
    for name,ds in result['disposition'].items():print(name,json.dumps(ds['All'],ensure_ascii=False),flush=True)
    for row in result['corroboration']:
        if row['stage']=='All':print('corroboration',json.dumps(row,ensure_ascii=False),flush=True)
    for name in ['thresholds','characteristics']:
        pd.DataFrame(result[name]).to_csv(OUT/(name+'_v2.csv'),index=False,encoding='utf-8-sig')
    print('Completed; participant data were not written to disk.',flush=True)
if __name__=='__main__':main()

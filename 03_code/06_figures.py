from pathlib import Path
import json
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.patches import Rectangle
from repro_paths import results_dir, figures_dir
R=Path(__file__).resolve().parents[1];O=figures_dir()
x=json.loads((results_dir()/'analysis_results_v2.json').read_text())
plt.rcParams.update({'font.family':'Arial','font.size':9,'axes.spines.top':False,'axes.spines.right':False,'axes.labelcolor':'#26343D','text.color':'#26343D','axes.edgecolor':'#687782','pdf.fonttype':42,'svg.fonttype':'none'})
names={'NACC_post2016':'NACC new entrants','ADNI':'ADNI','NACC_legacy':'NACC historical','ADNI_amyloid_positive':'ADNI amyloid positive'}
order=list(names);navy='#3E5568';teal='#577970';ochre='#9A7B50'
def save(f,n):
 f.savefig(O/f'{n}.pdf',bbox_inches='tight');f.savefig(O/f'{n}.svg',bbox_inches='tight')
 f.savefig(O/f'{n}.png',dpi=220,bbox_inches='tight')
 f.savefig(O/f'{n}.tif',dpi=1200,bbox_inches='tight',pil_kwargs={'compression':'tiff_lzw'});plt.close(f)
# Figure 1: independent display columns; A+ is explicitly a subset, never added to total.
f,axs=plt.subplots(1,4,figsize=(7.1,4.1)); f.subplots_adjust(wspace=.18,top=.90,bottom=.04,left=.01,right=.99)
for ax,k in zip(axs,order):
 d=x['disposition'][k]['All'];ax.set_xlim(0,1);ax.set_ylim(0,1);ax.axis('off');ax.text(.5,1.015,names[k],ha='center',va='bottom',fontweight='bold',fontsize=8.5)
 if k=='ADNI_amyloid_positive':ax.text(.5,.974,'Subset of ADNI',ha='center',fontsize=7.5,color=ochre)
 rows=[('Eligible baseline',d['baseline']),('Index assessment',d['index']),('Threshold crossed',d['crossers']),('Confirmation observed',d['observed'])]
 for j,(label,n) in enumerate(rows):
  y=.78-j*.22;ax.add_patch(Rectangle((.03,y),.94,.155,facecolor='white',edgecolor=navy,lw=.8));ax.text(.5,y+.101,label,ha='center',va='center',fontsize=7.9);ax.text(.5,y+.042,f'{n:,}',ha='center',va='center',fontweight='bold',fontsize=10)
  if j<3:ax.annotate('',xy=(.5,y-.054),xytext=(.5,y-.004),arrowprops={'arrowstyle':'->','color':navy,'lw':.8})
save(f,'Figure_1')
# Figure 2: stage-specific returner-conditional nonpersistence, primary cohort first.
f=plt.figure(figsize=(7.1,6));g=f.add_gridspec(1,3,width_ratios=[2.55,2.3,2.15],wspace=.03);a=f.add_subplot(g[0]);b=f.add_subplot(g[1]);c=f.add_subplot(g[2]);rows=[]
for k in order:
 for st in ['All','MCI','Mild dementia']:rows.append((k,st,x['disposition'][k][st]['nonpersistence_observed']))
for ax in [a,b,c]:ax.set_ylim(13.2,-.8)
a.axis('off');c.axis('off');b.set_xlim(0,70);b.set_xticks([0,20,40,60]);b.set_xlabel('Nonpersistence, %');b.set_yticks([]);b.spines['left'].set_visible(False);b.grid(axis='x',color='#E3E7E9',lw=.6,zorder=0)
a.text(0,-.7,'Cohort and baseline stage',fontweight='bold',fontsize=8.5);c.text(0,-.7,'n/N       % (95% CI)',fontweight='bold',fontsize=8.5)
for j,(k,st,r) in enumerate(rows):
 y=j+(j//3)*.45; color=navy if st=='All' else teal;lab=names[k] if st=='All' else '  '+st
 a.text(0,y,lab,va='center',fontweight='bold' if st=='All' else 'normal',fontsize=8.5)
 b.errorbar(100*r['risk'],y,xerr=[[100*(r['risk']-r['lo'])],[100*(r['hi']-r['risk'])]],fmt='o',markersize=4,color=color,elinewidth=1,capsize=2,zorder=3)
 c.text(0,y,f"{r['events']}/{r['n']}   {100*r['risk']:.1f} ({100*r['lo']:.1f}–{100*r['hi']:.1f})",va='center',fontsize=8.3)
f.subplots_adjust(left=.01,right=.99,top=.97,bottom=.1);save(f,'Figure_2')
# Figure 3: persistence by new functional dependency; same outcome throughout.
f=plt.figure(figsize=(7.1,4));g=f.add_gridspec(1,3,width_ratios=[2.1,2.6,2.4],wspace=.06);a=f.add_subplot(g[0]);b=f.add_subplot(g[1]);c=f.add_subplot(g[2]);
for ax in [a,b,c]:ax.set_ylim(4.7,-.6)
a.axis('off');c.axis('off');b.set_xlim(35,102);b.set_xticks([40,60,80,100]);b.set_xlabel('Persistent worsening, %');b.set_yticks([]);b.spines['left'].set_visible(False);b.grid(axis='x',color='#E3E7E9',lw=.6)
c.text(0,-.4,'Yes / No, n/N',fontweight='bold',fontsize=8.5)
for j,k in enumerate(order):
 d=next(t for t in x['corroboration'] if t['cohort']==k and t['stage']=='All');y=j*1.2
 a.text(0,y,names[k],va='center',fontsize=8.5)
 for dy,key,col,mark in [(-.14,'dependency_yes',navy,'o'),(.14,'dependency_no',ochre,'s')]:
  r=d[key];b.errorbar(100*r['risk'],y+dy,xerr=[[100*(r['risk']-r['lo'])],[100*(r['hi']-r['risk'])]],fmt=mark,color=col,markersize=4,elinewidth=1,capsize=2,zorder=3,label=('New dependency' if key.endswith('yes') else 'No new dependency') if j==0 else None)
  c.text(0,y+dy,f"{r['events']}/{r['n']}  ({100*r['risk']:.1f}%)",fontsize=8.5,va='center',color=col)
b.legend(loc='upper left',bbox_to_anchor=(-.65,-.16),ncol=2,frameon=False,fontsize=8)
f.subplots_adjust(left=.01,right=.99,top=.98,bottom=.22);save(f,'Figure_3')
# Supplement: all fixed cutoffs in both stages, without choosing favorable thresholds.
f,axs=plt.subplots(2,2,figsize=(7.1,6.1),sharex=True,sharey=True);f.subplots_adjust(hspace=.33,wspace=.25,bottom=.13,top=.94)
for ax,k,letter in zip(axs.flat,order,'ABCD'):
 for stage,color,off,marker in [('MCI',navy,-.035,'o'),('Mild dementia',ochre,.035,'s')]:
  ds=[r for r in x['thresholds'] if r['cohort']==k and r['stage']==stage];xx=np.array([r['threshold'] for r in ds])+off;yy=np.array([100*r['risk'] for r in ds]);lo=np.array([100*r['lo'] for r in ds]);hi=np.array([100*r['hi'] for r in ds]);ax.errorbar(xx,yy,yerr=[yy-lo,hi-yy],color=color,fmt=marker+'-',markersize=3.8,lw=.8,capsize=2,label=stage)
 ax.text(-.14,1.07,letter,transform=ax.transAxes,fontweight='bold',fontsize=10);ax.text(0,1.07,names[k],transform=ax.transAxes,fontsize=9)
 ax.set_xticks([.5,1,2,3]);ax.set_ylim(-2,100);ax.grid(axis='y',color='#E3E7E9',lw=.5)
for ax in axs[:,0]:ax.set_ylabel('Nonpersistence, %')
for ax in axs[1,:]:ax.set_xlabel('Fixed CDR-SB cutoff')
axs[0,0].legend(loc='upper left',frameon=False,fontsize=8)
save(f,'eFigure_1')
print('Four figures exported to PDF, SVG, PNG and 1200-dpi TIFF. Source: analysis_results_v2.json')

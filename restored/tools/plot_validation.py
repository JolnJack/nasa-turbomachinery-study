"""Plot printed reference values versus a recorded run; does not refit data."""
from pathlib import Path
import json,re,sys
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
ROOT=Path(__file__).resolve().parents[2];HERE=ROOT/'restored';RUN=Path(sys.argv[1])
ref=json.loads((HERE/'tests/reference_full.json').read_text());outdir=HERE/'validation'
plt.rcParams.update({'font.size':10,'axes.grid':True,'grid.alpha':.2,'svg.fonttype':'none'})
fig,axes=plt.subplots(1,2,figsize=(11,4.2),layout='constrained')
colors=['#2563eb','#08916b','#a855f7','#e58a18']
for speed,color in zip(['100','90','80','60'],colors):
 lines=(RUN/('compressor-'+speed+'.stdout')).read_text().splitlines();actual=[]
 for i,l in enumerate(lines):
  if 'WEQ' in l and 'PRESSURE RATIO' in l:actual.append(list(map(float,lines[i+1].split())))
 expected=ref['compressor'][speed]
 for ax,col in zip(axes,[1,2]):
  ax.plot([x[0] for x in actual],[x[col] for x in actual],color=color,label=speed+'% computed')
  ax.scatter([x[0] for x in expected],[x[col] for x in expected],facecolors='none',edgecolors=color,s=45)
for ax,ylabel in zip(axes,['Total pressure ratio','Total efficiency']):ax.set(xlabel='Equivalent mass flow (kg/s)',ylabel=ylabel)
axes[0].legend(ncol=2,fontsize=8);fig.suptitle('Compressor: 27-bit compatibility output vs NASA printed reference (open circles)')
fig.savefig(outdir/'compressor_reference.svg');fig.savefig(outdir/'compressor_reference.png',dpi=180);plt.close(fig)
fig,ax=plt.subplots(figsize=(7.3,4.4),layout='constrained')
expected=ref['turbine_table_v'];rows=[]
for l in (RUN/'turbine-short-table-III-coefficients.stdout').read_text().splitlines():
 try:v=list(map(float,l.split()))
 except ValueError:continue
 if len(v)==10:rows.append(v)
ax.plot([v[8] for v in rows],[v[4] for v in rows],label='Computed: Table III rounded coefficients',color='#2563eb')
ax.scatter([v[8] for v in expected],[v[4] for v in expected],label='NASA Table V as printed',facecolors='none',edgecolors='#555',s=45)
x,y=expected[8][8],expected[8][4];ax.scatter([x],[y],color='#d5413c',s=25)
ax.annotate('Printed 0.90378; same-row formula implies 0.900779',xy=(x,y),xytext=(2.7,.90),arrowprops={'arrowstyle':'->','color':'#d5413c'},fontsize=8,color='#a32e2e')
ax.set(xlabel='Equivalent total-to-static pressure ratio',ylabel='Total efficiency',title='Turbine: reference-table discrepancy remains visible');ax.legend(fontsize=8,loc='lower left')
fig.savefig(outdir/'turbine_reference.svg');fig.savefig(outdir/'turbine_reference.png',dpi=180)
(outdir/'plot-provenance.json').write_text(json.dumps({'run':str(RUN.resolve()),'data':'tests/reference_full.json','scope':'Computed reference tables, not independent experimental measurements. Plot overlap is not a zero-error proof.'},indent=2)+'\n')
print(outdir)

"""Known-root inverse checks using full-precision successful forward records."""
from pathlib import Path
import argparse, concurrent.futures, datetime, importlib.util, json, math, re

ROOT=Path(__file__).resolve().parents[2]
spec=importlib.util.spec_from_file_location('grid',Path(__file__).with_name('systematic_scan.py'))
grid=importlib.util.module_from_spec(spec);spec.loader.exec_module(grid)


def main():
    p=argparse.ArgumentParser();p.add_argument('grid',type=Path);p.add_argument('--workers',type=int,default=4);p.add_argument('--cases',type=Path);a=p.parse_args()
    source={c['id']:c for c in json.loads((a.grid/'cases.json').read_text())}
    records=[json.loads(x) for x in (a.grid/'results.jsonl').read_text().splitlines()]
    run=ROOT/'audit/2026-10-23/restoration'/('inverse-scan-'+datetime.datetime.now(datetime.timezone.utc).strftime('%Y%m%dT%H%M%S%fZ'));run.mkdir()
    paths={(name,model):a.grid/(name+'-'+model)/'program' for name in ['compressor','turbine'] for model in ['native32','compat27']}
    cases=[];selection=[]
    for r in sorted(records,key=lambda x:(x['id'],x['model'])):
        if r['program']!='turbine' or r['group']!='primary-grid' or r['model'] not in ['native32','compat27']:continue
        angle=float(re.search(r'\bB4\s*=\s*([-+0-9.Ee]+)',source[r['id']]['input'])[1])
        expected_cos=math.cos(angle*.01745329)
        eligible=[v for v in r['rows'] if all(math.isfinite(x) for x in v) and len(v)==28 and .35<=v[27]<=.75 and v[20]>0 and .2<v[21]<.99 and .2<v[22]<.99 and 1.05<v[23]<5 and 1.05<v[24]<8]
        valid=[v for v in eligible if abs(v[15]-expected_cos)<=2e-6]
        selection.append({'forward_id':r['id'],'model':r['model'],'eligible_points':len(eligible),'fixed_exit_angle_points':len(valid),'changed_exit_angle_points':len(eligible)-len(valid),'cosB4':expected_cos,'cosine_tolerance':2e-6,'reason':'Post-choke loading changes B4 in source label53; fixed-B4 design targets must retain the specified exit angle.'})
        if not valid:continue
        chosen=[valid[0]] if len(valid)==1 else [valid[0],valid[-1]]
        for j,v in enumerate(chosen):
            static=(j==1)
            target={'WD':v[20],'ETAD':v[22 if static else 21],'PDSGN':v[24 if static else 23],'ITEST':1 if static else 2,'MODE':2}
            text=source[r['id']]['input']
            for k,value in target.items():text=grid.override(text,k,format(value,'.17g') if isinstance(value,float) else value)
            case={'id':f'I{len(cases):05d}','program':'turbine','group':'known-root-inverse','input':text,'target':target,'forward_id':r['id'],'model':r['model'],'forward_coefficients':{'PD':v[25],'XK':v[26]},'forward_V1':v[27],'constraint':'fixed input B4; source post-choke angle changes excluded with recorded reason'}
            cases.append(case)
    if a.cases:
        cases=json.loads(a.cases.read_text())
        selection=[{'external_fixed_targets':str(a.cases),'reason':'Preserve the pre-guard known-root target set, including valid individual points after an invalid earlier batch point.'}]
    (run/'cases.json').write_text(json.dumps(cases,indent=2)+'\n')
    (run/'selection.json').write_text(json.dumps(selection,indent=2)+'\n')
    print('RESULTS',run,flush=True);print('PLANNED',len(cases),flush=True)
    result=[]
    def execute(case):
        row=grid.execute(run,paths,case,case['model']);target=case['target']
        row['forward_id']=case['forward_id'];row['target']=target
        if row['exit']!=0 or not row['rows']:
            row['inverse_status']='known-root-missed'
        else:
            v=row['rows'][-1];mass,etat,etas,z,z1,pd,xk,v1=v[20:]
            errors=[grid.relative(mass,target['WD']),abs((etas if target['ITEST']==1 else etat)-target['ETAD']),grid.relative(z1 if target['ITEST']==1 else z,target['PDSGN'])]
            row['target_errors']=errors;row['coefficients']={'PD':pd,'XK':xk}
            row['inverse_status']='matched' if all(e<=b for e,b in zip(errors,[3e-5,1e-4,1e-4])) and -1e-5<=xk and 0<pd<=1+1e-5 else 'target-or-coefficient-mismatch'
        return row
    with (run/'results.jsonl').open('w') as stream,concurrent.futures.ThreadPoolExecutor(max_workers=a.workers) as pool:
        for row in pool.map(execute,cases):
            result.append(row);stream.write(json.dumps(row)+'\n');stream.flush()
            if len(result)%100==0:print('COMPLETED',len(result),flush=True)
    counts={}
    for r in result:
        d=counts.setdefault(r['model'],{});d[r['inverse_status']]=d.get(r['inverse_status'],0)+1
    summary={'planned':len(cases),'completed':len(result),'counts':counts,'source_grid':str(a.grid),'source_cases':str(a.cases) if a.cases else None,'known_root_definition':'Target generated from same model forward equation at finite positive-work point; coefficients and source point retained. No experimental truth claimed.'}
    (run/'summary.json').write_text(json.dumps(summary,indent=2)+'\n');print(json.dumps(summary,indent=2),flush=True)


if __name__=='__main__':main()

"""Replay every stored known-root target; keep every search trace and failure."""
from pathlib import Path
import argparse, concurrent.futures, datetime, gzip, importlib.util, json

ROOT=Path(__file__).resolve().parents[2]
spec=importlib.util.spec_from_file_location('engineering_solver',ROOT/'restored/tools/turbine_design_solver.py')
solver=importlib.util.module_from_spec(spec);spec.loader.exec_module(solver)


def main():
    p=argparse.ArgumentParser();p.add_argument('cases',type=Path);p.add_argument('--limit',type=int);p.add_argument('--workers',type=int,default=4);a=p.parse_args()
    cases=json.loads(a.cases.read_text())
    if a.limit:cases=cases[:a.limit]
    run=ROOT/'audit/2026-10-23/restoration'/('engineering-inverse-'+datetime.datetime.now(datetime.timezone.utc).strftime('%Y%m%dT%H%M%S%fZ'));run.mkdir()
    (run/'cases.json').write_text(json.dumps(cases,indent=2)+'\n');(run/'traces').mkdir()
    paths={m:solver.build(run/m,m) for m in ['native32','compat27']}
    print('RESULTS',run,flush=True);print('PLANNED',len(cases),flush=True)
    def execute(case):
        result=solver.solve(case['input'],paths[case['model']])
        (run/'traces'/(case['id']+'.json.gz')).write_bytes(gzip.compress(json.dumps(result).encode()))
        row={k:v for k,v in result.items() if k not in ['trace','forward_input']}
        row.update(id=case['id'],model=case['model'],forward_id=case['forward_id'],target=case['target'])
        return row
    records=[]
    with (run/'results.jsonl').open('w') as stream,concurrent.futures.ThreadPoolExecutor(max_workers=a.workers) as pool:
        for row in pool.map(execute,cases):
            records.append(row);stream.write(json.dumps(row)+'\n');stream.flush()
            if len(records)%50==0:print('COMPLETED',len(records),flush=True)
    counts={}
    for row in records:
        d=counts.setdefault(row['model'],{});d[row['status']]=d.get(row['status'],0)+1
    summary={'planned':len(cases),'completed':len(records),'counts':counts,'source_cases':str(a.cases),'max_evaluations':max((r['evaluations'] for r in records),default=0),'mean_evaluations':sum(r['evaluations'] for r in records)/max(len(records),1),'known_root_coefficients_used_as_seeds':False}
    (run/'summary.json').write_text(json.dumps(summary,indent=2)+'\n');print(json.dumps(summary,indent=2),flush=True)
    raise SystemExit(0 if all(r['status']=='matched' for r in records) else 1)


if __name__=='__main__':main()

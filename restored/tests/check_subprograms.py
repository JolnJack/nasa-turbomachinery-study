from pathlib import Path
import subprocess,shutil,datetime,json,hashlib,sys
ROOT=Path(__file__).resolve().parents[2];SRC=ROOT/'restored'
run=ROOT/'audit/2026-10-23/restoration'/('subprograms-'+datetime.datetime.now(datetime.timezone.utc).strftime('%Y%m%dT%H%M%S%fZ'));run.mkdir()
paths=[]
compat="--compat27" in sys.argv
for prog,start in [('compressor_tn_d7487','      SUBROUTINE LININT'),('turbine_tn_d8063','      SUBROUTINE GETK')]:
 text=(SRC/('compat27/'+prog+'.f90' if compat else prog+'.f')).read_text();start=start.strip() if compat else start;part=text[text.index(start):];p=run/(prog+'-subprograms'+('.f90' if compat else '.f'));
 if compat:part=part.split('FUNCTION QBIT(VALUE)')[0]
 p.write_text(part);paths.append(str(p))
driver=SRC/'tests/subprograms.f'
if compat:
 text=(SRC/'compat27/compressor_tn_d7487.f90').read_text();primitive=text[text.index('FUNCTION QBIT(VALUE)'):];p=run/'primitive.f90';p.write_text(primitive);paths.append(str(p))
 driver=run/'driver.f';driver.write_text((SRC/'tests/subprograms.f').read_text().replace('EPSILON(EXACT)','1.1920929E-7'))
cmd=[shutil.which('gfortran'),'-std=legacy','-fno-automatic','-fcheck=all','-ffpe-trap=invalid,zero,overflow',*(['-fdefault-real-16','-ffree-line-length-none'] if compat else []),str(driver),*paths,'-o',str(run/'check')]
b=subprocess.run(cmd,capture_output=True);(run/'compile.stderr').write_bytes(b.stderr);assert b.returncode==0,b.stderr
r=subprocess.run([str(run/'check')],capture_output=True,timeout=5);(run/'stdout').write_bytes(r.stdout);(run/'stderr').write_bytes(r.stderr)
(run/'results.json').write_text(json.dumps({'command':cmd,'exit':r.returncode,'source_sha256':{p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in SRC.glob('*.f')},'scope':'FNTGRL degree 0..2, 18 lengths, all nodes; LININT bilinear surface; PABC quadratic; GETK/SEEKPR affine roots; CONTIN two roots/choking'},indent=2)+'\n')
print(r.stdout.decode());print(r.stderr.decode());print('RESULTS',run);raise SystemExit(r.returncode)

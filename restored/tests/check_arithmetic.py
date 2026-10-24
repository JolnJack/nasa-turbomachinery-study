"""Validate compatibility primitive against exact rational arithmetic, not host float rounding."""
from pathlib import Path
from fractions import Fraction
from decimal import Decimal,localcontext
import random,subprocess,shutil,json,datetime
ROOT=Path(__file__).resolve().parents[2];SRC=ROOT/'restored'
run=ROOT/'audit/2026-10-23/restoration'/('arithmetic-'+datetime.datetime.now(datetime.timezone.utc).strftime('%Y%m%dT%H%M%S%fZ'));run.mkdir()
def quant(x):
 if not x:return x
 sign=-1 if x<0 else 1;x=abs(x);e=x.numerator.bit_length()-x.denominator.bit_length()
 if x < Fraction(2)**e:e-=1
 step=Fraction(2)**(e-26)
 return sign*(x//step)*step
rng=random.Random(80637487);pairs=[]
for i in range(1000):
 def value():return rng.choice([-1,1])*Fraction(rng.randrange(2**26,2**27))*Fraction(2)**rng.randrange(-57,4)
 pairs.append((value(),value()))
with localcontext() as ctx:
 ctx.prec=200
 data=''.join(str(Decimal(a.numerator)/Decimal(a.denominator))+' '+str(Decimal(b.numerator)/Decimal(b.denominator))+'\n' for a,b in pairs)
(run/'operands.inp').write_text(data)
s=(SRC/'compat27/compressor_tn_d7487.f90').read_text();primitive=s[s.index('FUNCTION QBIT(VALUE)'):]
driver='''program check
real a,b,qbit
integer ios
do
read(*,*,iostat=ios) a,b
if(ios/=0) exit
write(*,'(4ES46.35)') qbit(a+b),qbit(a-b),qbit(a*b),qbit(a/b)
enddo
end program
'''+primitive
(run/'driver.f90').write_text(driver)
cmd=[shutil.which('gfortran'),'-fdefault-real-16','-ffree-line-length-none','-fcheck=all','-ffpe-trap=invalid,zero,overflow',str(run/'driver.f90'),'-o',str(run/'check')]
b=subprocess.run(cmd,capture_output=True);(run/'build.stderr').write_bytes(b.stderr);assert b.returncode==0,b.stderr
r=subprocess.run([str(run/'check')],input=data.encode(),capture_output=True,timeout=10);(run/'stdout').write_bytes(r.stdout);(run/'stderr').write_bytes(r.stderr)
assert r.returncode==0,r.stderr
rows=[list(map(float,line.split())) for line in r.stdout.decode().splitlines()];diff=[]
for i,((a,b),actual) in enumerate(zip(pairs,rows)):
 want=[float(quant(x)) for x in [a+b,a-b,a*b,a/b]]
 for j,(x,y) in enumerate(zip(want,actual)):
  if x!=y:diff.append({'row':i+1,'operation':j,'expected':x,'actual':y})
report={'cases':len(pairs),'actual_rows':len(rows),'exact_operations':4000-len(diff),'mismatches':diff,'command':cmd,'scope':'27-bit significand truncation; exact-rational add/subtract/multiply/divide over synthetic finite operands. Not an IBM machine certification.'}
(run/'results.json').write_text(json.dumps(report,indent=2)+'\n');print({k:v for k,v in report.items() if k not in ['command','scope']});print('RESULTS',run)
raise SystemExit(0 if len(rows)==1000 and not diff else 1)

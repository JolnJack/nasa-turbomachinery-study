"""Exploratory binary-precision sensitivity model, NOT an IBM CPU/compiler emulator.
Round real constants, input, intrinsics and expression operations to p fraction bits.
Historical evaluation order, library errors, accumulator/MQ and integer words are not emulated.
Never used as a production build or as an acceptance oracle.
"""
import ast,re,math,subprocess,json
from pathlib import Path
HERE=Path(__file__).resolve().parent;BASE=HERE.parents[1]/'2026-10-22/baseline'
# HERE is audit/2026-10-23/restoration; baseline is audit/2026-10-22/baseline.
BASE=HERE.parent.parent/'2026-10-22/baseline'
def logical_lines(s):
 records=[]
 for line in s.splitlines():
  if not line or line[0] in 'Cc*!':continue
  if len(line)>5 and line[5] not in ' 0':records[-1][1]+=line[6:72]
  else:records.append([line[:5].strip(),line[6:72]])
 return records
class Expr:
 def __init__(self,reals):self.reals=set(reals)
 def isint(self,name):return 'I'<=name[0]<='N' and name not in self.reals
 def emit(self,n):
  if isinstance(n,ast.Constant):
   if isinstance(n.value,int):return str(n.value),True
   return 'QBIT('+(repr(n.value).replace('e','D') if 'e' in repr(n.value) else repr(n.value)+'D0')+')',False
  if isinstance(n,ast.Name):return n.id,self.isint(n.id)
  if isinstance(n,ast.Call):
   name=n.func.id;args=[self.emit(x)[0] for x in n.args];v=name+'('+','.join(args)+')'
   integral=self.isint(name) if name not in ['ABS','COS','SIN','TAN','ATAN','ASIN','ARSIN','SQRT','EXP','FLOAT'] else False
   return (v if integral else 'QBIT('+v+')'),integral
  if isinstance(n,ast.UnaryOp):
   v,i=self.emit(n.operand);return ('-' if isinstance(n.op,ast.USub) else '+')+'('+v+')',i
  if isinstance(n,ast.BinOp):
   a,ia=self.emit(n.left);b,ib=self.emit(n.right);op={ast.Add:'+',ast.Sub:'-',ast.Mult:'*',ast.Div:'/',ast.Pow:'**'}[type(n.op)];v='('+a+op+b+')';i=ia and ib
   return (v if i else 'QBIT('+v+')'),i
  raise ValueError(ast.dump(n))
 def parse(self,s):return self.emit(ast.parse(s.strip(),mode='eval').body)[0]
def generate(bits,rounding):
 src=(BASE/'compressor_tn_d7487.f').read_text().replace('READ(5,INPUT)','READ(5,INPUT,END=900)')
 src=src.replace('IF(RMRMS.GE.MWRMS(I-1).AND.RMRMS.LE.MWRMS(I)) GO TO 80','IF(RMRMS.LE.MWRMS(I).OR.I.EQ.8) GO TO 80').replace('IF(RMRMS.GE.MWRMS(I-1).AND.RMRMS.LE.MWRMS(I)) GO TO 73','IF(RMRMS.LE.MWRMS(I).OR.I.EQ.8) GO TO 73')
 src=src.replace('  300 FORMAT','  900 STOP\n  300 FORMAT')
 records=logical_lines(src);e=Expr(['LAMX','LOD','MUO','NONDES','MWRMS','INC','N']);out=['      REAL QBIT'];in_main=True
 for label,text in records:
  t=text.strip()
  if t.startswith('SUBROUTINE') or t.startswith('FUNCTION'):
   in_main=False;e=Expr([]);out.append(t);out.append('REAL QBIT');continue
  if t.startswith('DATA'):
   # Binary real DATA literals; indices and dimensions stay integer.
   first=t.find('/');last=t.rfind('/')
   raw=t[first+1:last]
   def quant(m):
    x=float(m[0]);f,exp=math.frexp(x);q=math.trunc(math.ldexp(f,bits)) if rounding=='zero' else round(math.ldexp(f,bits));return repr(math.ldexp(q,exp-bits))+'D0'
   raw=re.sub(r'(?<![A-Z0-9])[-+]?(?:\d+\.\d*|\.\d+)(?:E[-+]?\d+)?',quant,raw)
   out.append(t[:first+1]+raw+t[last:]);continue
  if t.startswith(('DIMENSION','REAL','INTEGER','NAMELIST','FORMAT','READ','WRITE','GO TO','RETURN','END','STOP','CALL','CONTINUE')) or not t:
   out.append((label+' ' if label else '')+t)
  else:
   prefix='';body=t
   if t.startswith('IF(') or t.startswith('IF ('):
    start=t.index('(');depth=0;end=0
    for i in range(start,len(t)):
     if t[i]=='(':depth+=1
     if t[i]==')':depth-=1
     if depth==0:end=i+1;break
    prefix=t[:end]+' ';body=t[end:].strip()
   elif t.startswith('DO '):
    # DO bounds in these programs are integer; expression arithmetic is in body.
    out.append((label+' ' if label else '')+t);continue
   m=re.match(r'^([A-Z][A-Z0-9]*(?:\([^)]*\))?)\s*=\s*(.*)$',body)
   if m:
    target,rhs=m.groups();rhs=e.parse(rhs)
    if not e.isint(target.split('(')[0]):rhs='QBIT('+rhs+')'
    t=prefix+target+'='+rhs
   out.append((label+' ' if label else '')+t)
  if t.startswith('READ(5,INPUT') and in_main:
   names='GAM POP TOP N DIT MUO CF RGAS DRAT LAMX B2X Z VLDRR B2 B1MFB AR BLOCK AL3 ADTH NONDES AL1MF CHIH CHIT CURVH CURVT'.split()
   out.extend(x+'=QBIT('+x+')' for x in names)
   out.extend(['DO IQ=1,NVOVCR','VOVCR(IQ)=QBIT(VOVCR(IQ))','ENDDO'])
 out+=['FUNCTION QBIT(VALUE) RESULT(Q)','REAL VALUE,Q','IF(VALUE.EQ.0.) THEN','Q=0.','ELSE','Q=SCALE('+('AINT' if rounding=='zero' else 'ANINT')+'(SCALE(FRACTION(VALUE),'+str(bits)+')),EXPONENT(VALUE)-'+str(bits)+')','ENDIF','END FUNCTION']
 return '\n'.join(out)+'\n'
results=[]
for bits,rounding in [(24,'nearest'),(27,'zero'),(27,'nearest')]:
 label=str(bits)+'-'+rounding;f=HERE/('sensitivity-'+label+'.f90');f.write_text(generate(bits,rounding))
 exe=HERE/('sensitivity-'+label);cmd=['/opt/homebrew/bin/gfortran','-std=legacy','-fno-automatic','-fdefault-real-8','-fdefault-double-8','-ffree-line-length-none',str(f),'-o',str(exe)]
 b=subprocess.run(cmd,capture_output=True);(HERE/('sensitivity-'+label+'.build.stderr')).write_bytes(b.stderr)
 if b.returncode:print(label,'build error',b.stderr.decode()[:1800]);continue
 inp=(BASE/'compressor_tn_d7487.inp').read_bytes()
 try:r=subprocess.run([str(exe)],input=inp,capture_output=True,timeout=8)
 except subprocess.TimeoutExpired:print(label,'timeout');continue
 (HERE/('sensitivity-'+label+'.stdout')).write_bytes(r.stdout);(HERE/('sensitivity-'+label+'.stderr')).write_bytes(r.stderr)
 tri=[list(map(float,m)) for m in re.findall(r'WEQ\s+PRESSURE RATIO\s+ETAT\n\s*([\d.]+)\s+([\d.]+)\s+([\d.]+)',r.stdout.decode())]
 row={'bits':bits,'rounding':rounding,'exit':r.returncode,'points':len(tri),'60percent_third':tri[-7] if len(tri)==42 else None};results.append(row);print(row)
(HERE/'precision-sensitivity.json').write_text(json.dumps({'scope':__doc__,'cases':results},indent=2)+'\n')

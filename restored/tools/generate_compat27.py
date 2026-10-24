"""Generate an explicit 27-bit truncating arithmetic compatibility build.

This implements a specified arithmetic model, NOT an IBM CPU/compiler emulator.
Integer arithmetic, transcendental approximations, accumulator/MQ registers and
historical compiler evaluation order are not reconstructed. Sources remain the
reviewable fixed-form files. Each real expression operation is visible as QBIT.
Report-style G13 fields use five digits below 1 and six in fixed notation >=1,
matching the observed report presentation, without claiming historical ABI identity.
"""
from pathlib import Path
import argparse,ast,re,math,hashlib,json
from decimal import Decimal

def number(x):
 s=repr(x)
 return s.replace('e','D') if 'e' in s else s+'D0'
def qconstant(x,bits):
 if x==0:return x
 f,e=math.frexp(x)
 return math.ldexp(math.trunc(math.ldexp(f,bits)),e-bits)
def logical_lines(s):
 records=[]
 for line in s.splitlines():
  if not line or line[0] in 'Cc*!':continue
  if len(line)>5 and line[5] not in ' 0':records[-1][1]+=line[6:72]
  else:records.append([line[:5].strip(),line[6:72]])
 return records
class Expr:
 def __init__(self,bits):self.reals=set();self.ints=set();self.bits=bits;self.count=0
 def isint(self,name):return name in self.ints or ('I'<=name[0]<='N' and name not in self.reals)
 def emit(self,n):
  if isinstance(n,ast.Constant):
   if isinstance(n.value,int):return str(n.value),True
   return 'QBIT('+number(n.value)+')',False
  if isinstance(n,ast.Name):return n.id,self.isint(n.id)
  if isinstance(n,ast.Call):
   name=n.func.id;args=[self.emit(x) for x in n.args]
   if name=='EPSILON':return number(2.**(1-self.bits)),False
   if name=='IEEE_IS_FINITE':return name+'('+','.join(x[0] for x in args)+')',True
   if name in ['MAX','MIN','ABS','SIGN']:integral=all(x[1] for x in args)
   elif name in ['COS','SIN','TAN','ATAN','ASIN','ARSIN','SQRT','EXP','FLOAT','AMIN1']:integral=False
   else:integral=self.isint(name)
   v=name+'('+','.join(x[0] for x in args)+')'
   return (v if integral else 'QBIT('+v+')'),integral
  if isinstance(n,ast.UnaryOp):
   v,i=self.emit(n.operand)
   if isinstance(n.op,ast.Not):return '.NOT.('+v+')',True
   return ('-' if isinstance(n.op,ast.USub) else '+')+'('+v+')',i
  if isinstance(n,ast.BinOp):
   a,ia=self.emit(n.left);b,ib=self.emit(n.right);op={ast.Add:'+',ast.Sub:'-',ast.Mult:'*',ast.Div:'/',ast.Pow:'**'}[type(n.op)]
   v='('+a+op+b+')';integer=ia and ib;self.count+=not integer
   return (v if integer else 'QBIT('+v+')'),integer
  if isinstance(n,ast.BoolOp):return '('+('.AND.' if isinstance(n.op,ast.And) else '.OR.').join('('+self.emit(x)[0]+')' for x in n.values)+')',True
  if isinstance(n,ast.Compare):
   assert len(n.ops)==1
   op={ast.Lt:'.LT.',ast.LtE:'.LE.',ast.Gt:'.GT.',ast.GtE:'.GE.',ast.Eq:'.EQ.',ast.NotEq:'.NE.'}[type(n.ops[0])]
   return '('+self.emit(n.left)[0]+op+self.emit(n.comparators[0])[0]+')',True
  raise ValueError(ast.dump(n))
 def parse(self,s):
  for old,new in [('AND',' and '),('OR',' or '),('NOT',' not '),('GE','>='),('LE','<='),('GT','>'),('LT','<'),('EQ','=='),('NE','!=')]:s=s.replace('.'+old+'.',new)
  return self.emit(ast.parse(s.strip(),mode='eval').body)[0]
def split_args(s):
 out=[];start=0;depth=0
 for i,c in enumerate(s):
  depth+=(c=='(')-(c==')')
  if c==',' and depth==0:out.append(s[start:i].strip());start=i+1
 out.append(s[start:].strip());return out
def generate(src,bits,compressor):
 e=Expr(bits);out=[];needs_read_round=False;manifest=[]
 declarations=False
 for label,text in logical_lines(src):
  t=text.strip();original=t
  if t.startswith('USE'):
   out.append(t);continue
  if not declarations:
   out.extend(['REAL QBIT','CHARACTER*13 LEGACY_G13']);declarations=True
  if t.startswith(('SUBROUTINE','FUNCTION')):
   e.reals=set();e.ints=set();out.append(t);out.append('REAL QBIT');continue
  if t.startswith('REAL '):e.reals.update(x.strip() for x in t[5:].split(','))
  if t.startswith('INTEGER '):e.ints.update(x.strip() for x in t[8:].split(','))
  if t.startswith('DATA'):
   first=t.find('/');last=t.rfind('/');raw=t[first+1:last]
   raw=re.sub(r'(?<![A-Z0-9])[-+]?(?:\d+\.\d*|\.\d+)(?:E[-+]?\d+)?',lambda m:format(Decimal.from_float(qconstant(float(m[0]),bits)),'f')+'D0',raw)
   t=t[:first+1]+raw+t[last:]
  elif t.startswith(('DIMENSION','REAL','INTEGER','NAMELIST','CHARACTER','FORMAT','READ','WRITE','GO TO','RETURN','END','STOP','CALL','CONTINUE','ELSE')) or not t:
   if t.startswith('READ(CARDS,'):needs_read_round=True
   if not compressor:
    if label in ['400','500','501','505']:t=t.replace('G13.5','A13')
    m=re.match(r'WRITE\(6,(400|500|501|505)\)(.*)',t)
    if m:t='WRITE(6,'+m[1]+')'+','.join('LEGACY_G13('+v+')' for v in split_args(m[2]))
  else:
   prefix='';body=t
   if t.startswith('IF(') or t.startswith('IF ('):
    start=t.index('(');depth=0;end=0
    for i in range(start,len(t)):
     if t[i]=='(':depth+=1
     if t[i]==')':depth-=1
     if depth==0:end=i+1;break
    condition=t[start+1:end-1]
    # Domain validation arrays use modern Fortran array syntax; it is not part of the arithmetic model.
    if ':' not in condition and '(/' not in condition and not re.search(r'\b(ALL|ANY)\(',condition):condition=e.parse(condition)
    prefix='IF('+condition+') ';body=t[end:].strip();t=prefix+body
   elif t.startswith('DO '):
    out.append((label+' ' if label else '')+t);continue
   m=re.match(r'^([A-Z][A-Z0-9]*(?:\([^)]*\))?)\s*=\s*(.*)$',body)
   if m:
    target,rhs=m.groups();rhs=e.parse(rhs)
    if not e.isint(target.split('(')[0]):rhs='QBIT('+rhs+')'
    t=prefix+target+'='+rhs
  if not compressor:
   wm=re.search(r'WRITE\(6,(400|500|501|505)\)(.*)',t)
   if wm and 'LEGACY_G13(' not in wm[2]:t=t[:wm.start()]+'WRITE(6,'+wm[1]+')'+','.join('LEGACY_G13('+v+')' for v in split_args(wm[2]))
  if t!=original:manifest.append({'label':label,'original':original,'generated':t})
  out.append((label+' ' if label else '')+t)
  if needs_read_round and original=='IF(IOS.NE.0) GO TO 901':
   names=('GAM POP TOP N DIT MUO CF RGAS DRAT LAMX B2X Z VLDRR B2 B1MFB AR BLOCK AL3 ADTH NONDES AL1MF CHIH CHIT CURVH CURVT' if compressor else 'G P0 T0 A0 A1 A3 A5 D3 AL1 B4 BL1 BL4 PDSGN U3 U4U3 R V1 DELV VMAX XK WD ZZ PD ETAD DELY YMAX D2').split()
   out.extend(x+'=QBIT('+x+')' for x in names)
   if compressor:out.extend(['DO IQ=1,NVOVCR','IF(IQ.GT.15) EXIT','VOVCR(IQ)=QBIT(VOVCR(IQ))','ENDDO'])
   needs_read_round=False
 out+=['FUNCTION QBIT(VALUE) RESULT(Q)','USE, INTRINSIC :: IEEE_ARITHMETIC, ONLY: IEEE_IS_FINITE','REAL VALUE,Q','IF(.NOT.IEEE_IS_FINITE(VALUE)) THEN','Q=VALUE','ELSE IF(VALUE.EQ.0.) THEN','Q=VALUE','ELSE','Q=SCALE(AINT(SCALE(FRACTION(VALUE),'+str(bits)+')),EXPONENT(VALUE)-'+str(bits)+')','ENDIF','END FUNCTION']
 if not compressor:out+=['FUNCTION LEGACY_G13(VALUE) RESULT(FIELD)','REAL VALUE','CHARACTER*13 FIELD','IF(ABS(VALUE).GE.1..AND.ABS(VALUE).LT.1.E5) THEN',"WRITE(FIELD,'(G13.6)') VALUE",'ELSE',"WRITE(FIELD,'(G13.5)') VALUE",'ENDIF','END FUNCTION']
 return '! GENERATED: edit the fixed-form source and regenerate.\n'+'\n'.join(out)+'\n',manifest,e.count
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--source',type=Path,default=Path(__file__).resolve().parents[1]);p.add_argument('--output',type=Path);a=p.parse_args();dest=a.output or a.source/'compat27';dest.mkdir(exist_ok=True,parents=True)
 report={'model':__doc__,'bits':27,'rounding':'toward zero','sources':{}}
 for prog in ['compressor_tn_d7487','turbine_tn_d8063']:
  source=a.source/(prog+'.f');text,changes,n=generate(source.read_text(),27,prog.startswith('compressor'));out=dest/(prog+'.f90');out.write_text(text)
  report['sources'][prog]={'sha256':hashlib.sha256(source.read_bytes()).hexdigest(),'generated_sha256':hashlib.sha256(out.read_bytes()).hexdigest(),'real_binary_operations':n,'transformations':changes}
 (dest/'generation.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
 print('Generated',dest)

from pathlib import Path
p=Path('restored/compressor_tn_d7487.f');s=p.read_text()
s=s.replace('      CHARACTER*32768 CARDS','      USE, INTRINSIC :: IEEE_ARITHMETIC, ONLY: IEEE_IS_FINITE\n      CHARACTER*32768 CARDS',1)
real=['GAM','POP','TOP','N','DIT','MUO','CF','RGAS','DRAT','LAMX','B2X','Z','VLDRR','B2','B1MFB','AR','BLOCK','AL3','ADTH','NONDES','AL1MF','CHIH','CHIT','CURVH','CURVT']
data=''.join('      DATA '+','.join(real[i:i+4])+'/'+','.join(['0.']*len(real[i:i+4]))+'/\n' for i in range(0,len(real),4))+'      DATA NVOVCR,SPLT/-1,-1/,VOVCR/15*0./\n'
s=s.replace('      DATA ICASE/0/',data+'      DATA ICASE/0/')
checks=''
for name in real:checks+='      IF(.NOT.IEEE_IS_FINITE('+name+')) GO TO 902\n'
checks+='''      IF(NVOVCR.LT.1.OR.NVOVCR.GT.15) GO TO 902
      IF(.NOT.ALL(IEEE_IS_FINITE(VOVCR(1:NVOVCR)))) GO TO 902
      IF(GAM.LE.1..OR.RGAS.LE.0..OR.TOP.LE.0.) GO TO 902
      IF(POP.LE.0..OR.MUO.LE.0..OR.N.LE.0.) GO TO 902
      IF(DIT.LE.0..OR.B2.LE.0..OR.DRAT.LE.0.) GO TO 902
      IF(LAMX.LE.0..OR.LAMX.GE.1..OR.Z.LE.0.) GO TO 902
      IF(AR.LT.1.2.OR.AR.GT.5..OR.VLDRR.LE.1.) GO TO 902
      IF(ADTH.LE.0..OR.NONDES.LE.0..OR.CF.LT.0.) GO TO 902
      IF(BLOCK.LE.0..OR.BLOCK.GT.1.) GO TO 902
      IF(SPLT.NE.0.AND.SPLT.NE.1) GO TO 902
      IF(ANY(VOVCR(1:NVOVCR).LE.0.)) GO TO 902
      IF(ANY(VOVCR(1:NVOVCR).GE.
     1 SQRT((GAM+1.)/(GAM-1.)))) GO TO 902
'''
s=s.replace('      ICASE=ICASE+1',checks+'      ICASE=ICASE+1')
s=s.replace('  900 STOP',"  902 WRITE(0,*) 'INVALID COMPRESSOR INPUT DOMAIN'\n      STOP 1\n  900 STOP")
p.write_text(s)
p=Path('restored/turbine_tn_d8063.f');s=p.read_text().replace('      CHARACTER*6 NAME(10),CASE(10)','      USE, INTRINSIC :: IEEE_ARITHMETIC, ONLY: IEEE_IS_FINITE\n      CHARACTER*6 NAME(10),CASE(10)',1)
real=['G','P0','T0','A0','A1','A3','A5','D3','AL1','B4','BL1','BL4','PDSGN','U3','U4U3','R','V1','DELV','VMAX','XK','WD','ZZ','PD','ETAD','DELY','YMAX','D2']
data=''.join('      DATA '+','.join(real[i:i+4])+'/'+','.join(['0.']*len(real[i:i+4]))+'/\n' for i in range(0,len(real),4))+'      DATA MODE,ITEST/-1,-1/\n'
s=s.replace('      SUBR(X,G)=',data+'      SUBR(X,G)=',1)
checks=''
for name in real:checks+='      IF(.NOT.IEEE_IS_FINITE('+name+')) GO TO 902\n'
checks+='''      IF(MODE.LT.0.OR.MODE.GT.5) GO TO 902
      IF(G.LE.1..OR.P0.LE.0..OR.T0.LE.0..OR.R.LE.0.) GO TO 902
      IF(MIN(A0,A1,A3,A5,D2,D3,U3,ZZ).LE.0.) GO TO 902
      IF(BL1.LE.0..OR.BL1.GT.1.) GO TO 902
      IF(BL4.LE.0..OR.BL4.GT.1.) GO TO 902
      IF(U4U3.LE.0..OR.U4U3.GE.1.) GO TO 902
      IF(ABS(AL1).GE.90..OR.ABS(B4).GE.90.) GO TO 902
      IF(V1.LE.0..OR.VMAX.LT.V1.OR.DELV.LE.0.) GO TO 902
      IF(DELY.LE.0..OR.YMAX.LE.0.) GO TO 902
      IF(MODE.EQ.2.OR.MODE.EQ.5) THEN
        IF(ITEST.NE.1.AND.ITEST.NE.2) GO TO 902
        IF(WD.LE.0..OR.PDSGN.LE.1.) GO TO 902
        IF(ETAD.LE.0..OR.ETAD.GT.1.) GO TO 902
      ELSE
        IF(PD.LE.0..OR.PD.GT.1..OR.XK.LT.0.) GO TO 902
      ENDIF
'''
s=s.replace('      WRITE(6,200)NAME,CASE',checks+'      WRITE(6,200)NAME,CASE')
s=s.replace('      V1VC1=.5',"      IF(SS.GT.SUBR(1.,G)) THEN\n        WRITE(0,*) 'DESIGN FLOW EXCEEDS STATOR CAPACITY'\n        STOP 2\n      ENDIF\n      V1VC1=.5",1)
s=s.replace('  900 STOP',"  902 WRITE(0,*) 'INVALID TURBINE INPUT DOMAIN'\n      STOP 1\n  900 STOP")
p.write_text(s)

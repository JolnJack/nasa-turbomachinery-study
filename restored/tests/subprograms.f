      PROGRAM CHECK_SUBPROGRAMS
      DIMENSION F(20),S(20),X(4),Y(6),TAB(4,6),PX(3),PY(3)
      INTEGER FAIL
      FAIL=0
C     Polynomials have analytic integrals; use a roundoff-scaled bound.
      DO 30 N=3,20
      DO 30 K=0,2
      H=.2
      DO 10 I=1,N
   10 F(I)=(FLOAT(I-1)*H)**K
      CALL FNTGRL(N,H,F,S)
      DO 20 I=1,N
      EXACT=(FLOAT(I-1)*H)**(K+1)/FLOAT(K+1)
      IF(ABS(S(I)-EXACT).GT.
     1 64.*EPSILON(EXACT)*(1.+ABS(EXACT))) FAIL=FAIL+1
   20 CONTINUE
   30 CONTINUE
C     A bilinear surface is exactly reproduced, including end intervals.
      DO 40 I=1,4
   40 X(I)=FLOAT(I)/5.
      DO 50 J=1,6
   50 Y(J)=FLOAT(J)/50.
      DO 60 I=1,4
      DO 60 J=1,6
   60 TAB(I,J)=2.*X(I)+3.*Y(J)+4.*X(I)*Y(J)
      DO 70 I=0,10
      XX=FLOAT(I)/10.
      YY=.01*FLOAT(I+1)
      CALL LININT(XX,YY,X,Y,TAB,4,6,VALUE)
      EXACT=2.*XX+3.*YY+4.*XX*YY
      IF(ABS(VALUE-EXACT).GT.2.E-6) FAIL=FAIL+1
   70 CONTINUE
      PX(1)=-2.
      PX(2)=.5
      PX(3)=3.
      DO 80 I=1,3
   80 PY(I)=1.5*PX(I)**2-2.*PX(I)+7.
      CALL PABC(PX,PY,A,B,C)
      IF(ABS(A-1.5).GT.1.E-6) FAIL=FAIL+1
      IF(ABS(B+2.).GT.1.E-6) FAIL=FAIL+1
      IF(ABS(C-7.).GT.1.E-6) FAIL=FAIL+1
      XK=.1
      IK=1
      CALL GETK(XK,1.-2.*XK,.795,IK)
      CALL GETK(XK,1.-2.*XK,.795,IK)
      IF(IK.NE.5.OR.ABS(XK-.1025).GT.1.E-6) FAIL=FAIL+1
      PD=1.
      IL=1
      CALL SEEKPR(1.005,3.-2.*PD,PD,IL)
      CALL SEEKPR(1.005,3.-2.*PD,PD,IL)
      IF(IL.NE.5.OR.ABS(PD-.9975).GT.1.E-6) FAIL=FAIL+1
C     Concave mass-flow analogue: two known roots and a choked maximum.
      DO 110 JZ=1,2
      XX=.3
      IND=1
      DO 100 ITER=1,110
      VALUE=XX*(2.-XX)
      IF(IND.GE.6.AND.ABS(VALUE-.75).LT.1.E-6) GO TO 105
      CALL CONTIN(XX,VALUE,IND,JZ,.75,.1)
      IF(IND.GE.10) GO TO 105
  100 CONTINUE
  105 EXACT=.5
      IF(JZ.EQ.2) EXACT=1.5
      IF(ABS(XX-EXACT).GT.1.E-5) FAIL=FAIL+1
      IF(IND.GE.10) FAIL=FAIL+1
  110 CONTINUE
      XX=.3
      IND=1
      DO 120 ITER=1,110
      VALUE=XX*(2.-XX)
      CALL CONTIN(XX,VALUE,IND,1,1.1,.1)
      IF(IND.GE.10) GO TO 125
  120 CONTINUE
  125 IF(IND.NE.10.OR.ABS(XX-1.).GT.1.E-5) FAIL=FAIL+1
      WRITE(*,*) 'SUBPROGRAM FAILURES:',FAIL
      IF(FAIL.NE.0) STOP 1
      END

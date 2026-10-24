      SUBROUTINE LININT (X1,Y1,X,Y,TN,MX,MY,F)
      DIMENSION X(MX), Y(MY), TN(MX,MY)
      DO 1 J3=2,MX
    1 IF (X1.LE.X(J3)) GO TO 2
      J3=MX
    2 DO 3 J4=2,MY
    3 IF (Y1.LE.Y(J4)) GO TO 4
      J4=MY
    4 J1=J3-1
      J2=J4-1
      EPS1=(X1-X(J1))/(X(J3)-X(J1))
      EPS2=(Y1-Y(J2))/(Y(J4)-Y(J2))
      EPS3=1.-EPS1
      EPS4=1.-EPS2
      F=TN(J1,J2)*EPS3*EPS4+TN(J3,J2)*EPS1*EPS4+TN(J1,J4)*EPS2*EPS3+TN(J
     13,J4)*EPS1*EPS2
      RETURN
      END
      SUBROUTINE FNTGRL(NO,DELTAR,F,S)
      DIMENSION F(20),S(20)
      S(1)=0.
      S(2)=DELTAR*(5.*F(1)+8.*F(2)-F(3))/12.
      DO 1 I=3,NO
    1 S(I)=S(I-1)+DELTAR*(5.*F(I)+8.*F(I-1)-F(I-2))/12.
      RETURN
      END
      FUNCTION ARSIN(X)
      ARSIN=ASIN(X)
      RETURN
      END

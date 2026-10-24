      PROGRAM VERIFYF
      DIMENSION F(20),S(20)
      DO 20 K=0,2
      DO 10 I=1,11
      X=FLOAT(I-1)/4.
      F(I)=X**K
   10 CONTINUE
      CALL FNTGRL(11,.25,F,S)
      DO 15 I=1,11
      X=FLOAT(I-1)/4.
      EXACT=X**(K+1)/FLOAT(K+1)
      WRITE(*,*) K,I,S(I),EXACT,ABS(S(I)-EXACT)
   15 CONTINUE
   20 CONTINUE
      END
      SUBROUTINE FNTGRL(NO,DELTAR,F,S)
      DIMENSION F(20),S(20)
      S(1)=0.
      S(2)=DELTAR*(5.*F(1)+8.*F(2)-F(3))/12.
      DO 1 I=3,NO
    1 S(I)=S(I-1)+DELTAR*(5.*F(I)+8.*F(I-1)-F(I-2))/12.
      RETURN
      END

      PROGRAM ENDPOINT
      V=.30
      STEP=.05
      VMAX=.80
      DO 10 I=1,11
      WRITE(*,'(I3,2ES20.10,L3)') I,V,VMAX,V.GT.VMAX
      V=V+STEP
   10 CONTINUE
      END

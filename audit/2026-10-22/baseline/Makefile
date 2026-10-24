FC = /opt/homebrew/bin/gfortran
FFLAGS = -std=legacy -fno-automatic -w

.PHONY: all run clean
all: compressor_tn_d7487 turbine_tn_d8063

compressor_tn_d7487: compressor_tn_d7487.f
	$(FC) $(FFLAGS) $< -o $@

turbine_tn_d8063: turbine_tn_d8063.f
	$(FC) $(FFLAGS) $< -o $@

run: all
	./compressor_tn_d7487 < compressor_tn_d7487.inp > compressor_tn_d7487.out 2>/dev/null || true
	./turbine_tn_d8063 < turbine_tn_d8063.inp > turbine_tn_d8063.out 2>/dev/null || true

clean:
	rm -f compressor_tn_d7487 turbine_tn_d8063

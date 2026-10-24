ifeq ($(origin FC),default)
FC = gfortran
endif
FC ?= gfortran
PYTHON ?= python3
CHECK_FLAGS = -std=legacy -fno-automatic -fcheck=all -fbacktrace -ffpe-trap=invalid,zero,overflow
COMPAT_FLAGS = $(CHECK_FLAGS) -fdefault-real-16 -ffree-line-length-none
PROGRAMS = compressor_tn_d7487 turbine_tn_d8063
COMPAT = $(addprefix build/compat27/,$(PROGRAMS))
NATIVE = $(addprefix build/native32/,$(PROGRAMS))
MODERN = $(addprefix build/modern64/,$(PROGRAMS))
.PHONY: all native modern generate run test test-functional test-reference test-arithmetic test-conservation test-subprograms historical run-historical test-historical test-new-data test-design test-design-scan scan
all: $(COMPAT)
native: $(NATIVE)
modern: $(MODERN)
generate: compat27/generation.json
compat27/generation.json: compressor_tn_d7487.f turbine_tn_d8063.f tools/generate_compat27.py
	$(PYTHON) tools/generate_compat27.py
build/compat27/%: compat27/generation.json read_namelist_cards.f90
	@mkdir -p build/compat27 build/logs
	$(FC) $(COMPAT_FLAGS) compat27/$*.f90 read_namelist_cards.f90 -o $@ >build/logs/$*-compat27.txt 2>&1
build/native32/%: %.f read_namelist_cards.f90
	@mkdir -p build/native32 build/logs
	$(FC) $(CHECK_FLAGS) $< read_namelist_cards.f90 -o $@ >build/logs/$*-native32.txt 2>&1
build/modern64/%: %.f read_namelist_cards.f90
	@mkdir -p build/modern64 build/logs
	$(FC) $(CHECK_FLAGS) -fdefault-real-8 -fdefault-double-8 $< read_namelist_cards.f90 -o $@ >build/logs/$*-modern64.txt 2>&1
run: all
	@mkdir -p build/output
	./build/compat27/compressor_tn_d7487 < examples/compressor_original.inp > build/output/compressor.out
	./build/compat27/turbine_tn_d8063 < examples/turbine_original.inp > build/output/turbine.out
test-integrity: generate
	$(PYTHON) tests/verify_integrity.py
test-functional: test-integrity
	$(PYTHON) tests/regression.py --compat27 --quad --tag functional
test-arithmetic: generate
	$(PYTHON) tests/check_arithmetic.py
test-subprograms: generate
	$(PYTHON) tests/check_subprograms.py
	$(PYTHON) tests/check_subprograms.py --compat27
test-conservation: generate
	$(PYTHON) tests/check_conservation.py
test-reference: generate
	$(PYTHON) tests/compare_full.py --compat27 --quad
test: test-integrity test-functional test-arithmetic test-subprograms test-conservation test-reference
historical:
	$(PYTHON) tools/prepare_historical.py
run-historical: historical
	$(PYTHON) tools/run_historical_turbine.py --portable-formats --library-source --formatted-input --dump-words --input examples/turbine_design_then_offdesign.inp
test-historical: test-integrity historical
	$(PYTHON) tests/check_historical.py
test-new-data: test-integrity historical
	$(PYTHON) tests/try_new_data.py
test-design:
	$(PYTHON) tests/check_design_interface.py
test-design-scan:
	$(PYTHON) tests/check_design_solver.py tests/fixtures/turbine_known_roots.json
scan:
	$(PYTHON) tests/systematic_scan.py --models native32 compat27 modern64

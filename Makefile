.DEFAULT_GOAL := help
PYTHON ?= python3

.PHONY: help all modern native run check test test-functional test-reference test-arithmetic test-subprograms test-conservation test-design test-design-scan scan historical test-historical run-historical test-new-data
help:
	@echo 'NASA 两份报告学习与程序复原项目'
	@echo 'make modern          构建64位工程候选版'
	@echo 'make run             构建27位兼容版并运行公开样例'
	@echo 'make check           核查目录、原件哈希和生成源'
	@echo 'make test-functional 运行功能回归'
	@echo 'make test            完整严格检查（透平原表对照仍有已知失败）'
	@echo '其他目标和使用边界见 README.md、restored/README.md'

all: modern
check:
	$(PYTHON) tools/check_project.py
	$(MAKE) -C restored test-integrity
modern native run test test-functional test-reference test-arithmetic test-subprograms test-conservation test-design test-design-scan scan historical test-historical run-historical test-new-data:
	$(MAKE) -C restored $@

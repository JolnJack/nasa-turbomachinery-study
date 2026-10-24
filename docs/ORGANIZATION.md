# 项目整理说明

2026-10-23：把根目录混放的原始文件按用途搬迁，保留 `restored/` 和日期化审计结构，以减少依赖路径变动。

| 原位置 | 新位置 |
| --- | --- |
| 根目录两份 PDF | `reports/` |
| 根目录三份教程与指南 | `docs/tutorials/` |
| 根目录旧源码、输入输出、可执行文件、Makefile | `originals/` |
| `RESTORATION_STATUS.md` | `docs/STATUS.md` |

根目录新 Makefile 统一转发到修复版，默认显示帮助。完整性检查、历史后端输入路径和守恒检查路径已随搬迁更新。原始14文件内容、基线副本、现代 Fortran 公式及固定参考数据不变。

精简时删除的历史明细不在本次整理中补造。已删除外部归档的说明已更新，不能继续把旧恢复路径当作可用备份。

Git 中先保存了整理前的可追溯状态；逐文件搬迁哈希与该提交号见 [relocation.json](../audit/organization-2026-10-23/relocation.json)。早期教程和旧审计记录原样保留，其中旧绝对路径反映当时位置。

重新检查：

```sh
make check
make modern
make run
make test-functional
```

本次整理不改变科学验收状态。现代透平严格原表对照的已知失败仍须如实保留。

干净目录重建结果见 [verification.json](../audit/organization-2026-10-23/verification.json)，原始标准输出、错误输出及各项检查摘要保存在同目录。严格参考表失败作为预期的未通过项单列，不计为软件整体通过。

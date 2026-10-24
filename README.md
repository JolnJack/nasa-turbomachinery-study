# NASA 叶轮机械报告学习与程序复原

围绕 NASA TN D-7487 离心压气机和 TN D-8063 向心透平报告，保存原始资料、本地转录、现代修复版、零基础教程和验证证据。

**当前定位：可用于学习、公开算例复核和限定范围的科研探索。整体尚未最终验收，不能称为与未取得的 NASA 分发源文件完全相同，也未完成你们具体 He–Xe 机组的独立物理验证。**

## 从这里开始

| 想做什么 | 入口 |
| --- | --- |
| 从零开始学习 | [教程目录与阅读顺序](docs/README.md) |
| 阅读 NASA 原报告 | [报告目录](reports/README.md) |
| 构建、运行、更换输入 | [现代修复版使用说明](restored/README.md) |
| 判断哪些检查通过、哪些仍失败 | [当前状态](docs/STATUS.md)、[扫描报告](restored/SCAN_RESULTS.md) |
| 核对转录原件及其位置 | [原始文件说明](originals/README.md)、[位置和哈希清单](originals/manifest.json) |
| 查阅审计与历史证据 | [审计目录说明](audit/README.md) |

## 目录

```text
NASA/
├── README.md        阅读与运行入口
├── Makefile         统一命令入口
├── reports/         两份 NASA 原始 PDF
├── docs/            教程、当前状态、整理说明
├── originals/       原始本地转录、输入输出、旧构建文件
├── restored/        现代修复源码、示例、测试、工具及验证报告
├── audit/           日期化审计证据、原始基线与整理核验
└── tools/           项目结构与完整性检查
```

目录整理没有修改原始文件内容、Fortran 计算公式或冻结的参考数据。搬迁记录见 [整理说明](docs/ORGANIZATION.md)。

## 构建和运行

需要 Python 3 和支持相关精度选项的 GNU Fortran。以下命令均在仓库根目录执行：

```sh
make check
make modern
make run
make test-functional
```

- `make modern`：64位工程候选版位于 `restored/build/modern64/`，适合新数据的离线探索。
- `make run`：27位兼容版运行原始样例，输出位于 `restored/build/output/`。
- `make test`：包含严格原表比较，**现代透平仍有已知差异，当前预期返回非零**。功能回归通过不能替代这一项。
- 不要用 `originals/Makefile` 作为修复版入口；它保留了早期会隐藏运行错误的行为。

例如用64位版运行一份新输入：

```sh
restored/build/modern64/compressor_tn_d7487 < restored/examples/compressor_new_data.inp > restored/build/compressor-new.out
```

程序返回成功也需要检查输出是否包含有效性能点、收敛与守恒是否满足规则。完整输入和逆设计工具说明见 [restored/README.md](restored/README.md)。

## 验证边界

现存记录包括61项功能回归、压气机470个参考打印值对照、4992次已列网格进程运行，以及1126项工程逆设计目标检查。它们是不同层次的数值证据，不能合并称作实验验证。详细拒绝、无输出和失败分类保留在 [扫描报告](restored/SCAN_RESULTS.md)。

原报告公式与印刷表矛盾时采用公式和程序清单优先，原表保留，勘误候选见 [ERRATA.md](restored/ERRATA.md)。历史审计明细曾移入外部归档，该归档已被用户删除；仓库保留当前仍存在的摘要和证据，不能恢复已删除的完整轨迹。

Git 忽略可重建的现代构建目录、缓存和可选历史运行环境。少量原始可执行文件作为基线证据保存，不作为跨平台分发程序。仓库不替原始报告或第三方运行环境另行授予许可证。

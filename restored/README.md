# NASA 文档功能复原版

以下命令在仓库根目录执行。原始本地文件现在位于 `originals/`，两份报告在 `reports/`；原件位置及哈希见 [清单](../originals/manifest.json)。历史明细归档已删除，当前可用证据范围见 [审计说明](../audit/README.md)。

状态（2026-10-23）：**已形成可构建、可重跑的修复版；整体尚未最终验收。** 压气机公开样例 470 个打印值已全部相同。新增透平历史后端：原表 424/425 相同，唯一差异为有独立公式证据的勘误候选；按用户选定的公式优先口径，该组参考算例通过。现代 compat27 透平仍有差异，不能将两个后端的验证范围混用。

用户已选择：公式、程序清单优先；保留原表，文档矛盾单列证据。这里没有修改原始 PDF、本地转录源码、原始输入或原始输出。

2026-10-24 教程核查补充：SI 透平 `N` 的实际数值为 rev/s，`TOR` 等约有60倍尺度偏差，`NS` 约为通常 SI 定义的1/60。代码尚未修正这一历史换算，不能直接用于轴系/比转速选型。压气机扩压器推进次数与正文描述也须分开理解。详见[清单差异与单位说明](../docs/CODE_CAVEATS.md)。

## 扩展扫描与工程求解

新增 [完整扫描报告](SCAN_RESULTS.md) 和事先列定的 [扫描范围](SCAN_PLAN.md)。不能把扫描执行完成、明确拒绝输入或“未到堵塞所以无输出”统计为性能计算通过。原单精度和兼容精度在部分低功点仍超出守恒残差规则；新增64位工程构建在同一网格的有效输出中通过原规则，但不用于替代历史逐位对照。

```sh
make -C restored modern
make -C restored scan
make -C restored test-design
make -C restored test-design-scan
python3 restored/tools/turbine_design_solver.py --input restored/examples/turbine_known_root_design.inp --output restored/build/my-design
```

`modern` 的可执行文件在 `build/modern64/`。工程逆设计工具要求一份完整的单组 MODE=2/5 输入，支持总对总/总对静、SI/英制；输出目录必须尚不存在。它保留完整搜索过程、残差、构建源和编译参数，成功时生成 `computed-output.txt`。一般解保存 `solved.inp`；堵塞附近的代数方程解保存 `equation-input.inp`，必须用同目录 `algebraic-full` 重跑，不能把它交回旧 CONTIN 求根程序后假定结果相同。对应诊断在 `equation-audit.txt`，后端标识在 `result.json`。输入的 PD/K 不作为已知初值或答案。

这是独立工程搜索改进，未替换旧 Fortran MODE=2/5 搜索，也不冒充NASA逐字源代码。旧入口新增200000次总迭代预算，无法完成时明确非零退出；资源上限不构成数学无解证明。精确静叶容量边界、任意超音速分支、多解穷尽搜索和所有几何组合仍未认证。

## 构建与运行

需要 GNU Fortran（本机 gfortran 16.2.0，Apple Silicon）和 Python 3。默认构建采用显式 27 位尾数截断算术，以 128 位实数承载运算后量化。编译器需支持 `-fdefault-real-16`，不承诺在未经测试的其他编译器/平台上完全相同。

```sh
make -C restored run
make -C restored native
make -C restored test-functional
make -C restored test
make -C restored test-historical
make -C restored run-historical
make -C restored test-new-data
```

- 默认可执行文件：`build/compat27/`；输出：`build/output/`。
- 原生单精度对照版：`build/native32/`。它仍有已记录的历史参考差异。
- 编译日志：`build/logs/`；运行错误直接输出到 stderr，失败状态不会被吞掉。
- `make test` 包含未修改的原表严格比较，**当前会在透平原表对照返回失败**；这是未完成验收的真实状态。
- 61 项功能回归、算术、子程序、守恒检查分别有独立目标，详见 Makefile。不能把这些子集通过写成整个项目通过。
- 历史后端在独立 IBM 7094/IBSYS 仿真中运行透平计算主体；输入输出接口有显式适配。`run-historical` 使用设计内部系数直接继承示例，返回作业目录及 `computed-output.txt`。首次准备需要 C 编译器和 make，档案按固定哈希验证。详见 `TURBINE_FINDINGS.md`；不是现代修复版的所有防护功能均在历史后端通过。

## 文件与来源

`compressor_tn_d7487.f`、`turbine_tn_d8063.f` 是可审查的修复源；`read_namelist_cards.f90` 负责输入记录检查。所有理论关联式、经验常数和原清单迭代容差保持其历史定义。

`tools/generate_compat27.py` 从修复源生成 `compat27/*.f90`，`generation.json` 记录逐条变换与源码哈希。修改固定格式源后重新生成，不手工修改生成文件。

这是一种明确规定的数值兼容模型，**不是完整 IBM CPU、原编译器或原数学库仿真**。它没有重建寄存器/MQ、历史指数溢出、整数机器字及库函数近似。幂运算与初等函数在承载类型求值后量化，不能由公开算例通过推导所有输入都与历史机器逐位相同。透平的 G13 报告显示格式有单独适配，并未据此推断历史编译器 ABI。

`examples/*_original.inp` 与 originals/ 中原始输入哈希相同。`turbine_table_III_coefficients.inp` 明确使用 Table III 的舍入系数，属于诊断对照输入，不冒充 Table II 原输入。

`examples/turbine_design_then_offdesign.inp` 在设计求解后只指定 MODE=0/1，保留完整内部 XK/PD。它可用于两个后端；现代 compat27 采用该输入后长表 161/165、短表 193/200，历史后端分别为 165/165、199/200。后者唯一差异保留在勘误记录中。

## 实际证据

完整报告见 `VALIDATION.md`，修正依据见 `SOURCE_MAP.md`，文档矛盾见 `ERRATA.md`。测试数据由原页独立人工转录；模糊数字经过局部放大复核，更正记录保留。

本轮边界：公开表格对照、列出的功能与边界诊断、数学子程序、算术兼容原语、透平守恒关系。实验实测曲线没有被当作程序计算表；尚未完成所有实验图的数字化和适用域的穷尽验证。历史关联式及清单近似本身也不等于现代设计模型的物理正确性证明。

更换数据的实际运行见 `NEW_DATA_TRIAL.md`：新压气机6个性能点、新透平20工况完成；首轮逆设计失败也保留，并新增了失败后阻止无效状态沿用的回归。历史包装器会把实际无解及库函数错误返回为失败。

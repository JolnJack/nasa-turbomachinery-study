# 教程修订核验

开始于 2026-10-23，完成核验于 2026-10-24。范围是三份教程、导航说明及文档检查，不是重新完成全项目科学验收。

## 本次实际执行

- `make modern`：成功，现有构建已是最新。
- modern64 压气机运行 `restored/examples/compressor_original.inp`：退出 0，stderr 为空，完整输出见 [compressor.out](compressor.out)。首条有效性能点为 `WEQ=.616 / PR=6.485 / ETAT=.768`。
- modern64 透平运行 `restored/examples/turbine_design_then_offdesign.inp`：退出 0，stderr 为空，完整输出见 [turbine.out](turbine.out)。设计后直接继承内部系数。
- 从修订后的 Markdown 直接提取完整输入块，另行执行：[压气机输入](embedded-compressor.inp)得到 12 个性能块；[透平输入](embedded-turbine.inp)得到 21 个长输出块，另有短表。均退出 0 且无 stderr。
- `turbine_design_solver.py --input restored/examples/turbine_known_root_design.inp --output restored/build/tutorial-design`：默认 compat27，7 次评估，状态 `matched`，`forward-full` 重放退出 0。见[结果及残差](design-result.json)、[重放输入](design-solved.inp)、[重放输出](design-computed-output.txt)。这些复制文件用于核验；重跑时应在工具生成目录使用对应可执行后端。
- 独立核算压气机叶尖速度、临界速度和八项损失之和；核算透平功率、几何角速度及扭矩，记录在 [verification.json](verification.json)。

原始三份教程在修改前复制到 `originals/tutorials/`，位置清单更新但原始 SHA-256 不变。两份修复版 Fortran 计算源和输入读取器的哈希均与本轮开始的 Git HEAD 相同。完整性与链接检查见 [project-check.txt](project-check.txt)。

## 使用边界

本轮没有改动历史公式、参考表、积分循环或 SI 派生输出；单位问题和积分终点差异见 [CODE_CAVEATS.md](../../docs/CODE_CAVEATS.md)。全套网格扫描、历史环境运行及严格原表验收没有在本轮重做，现代透平参考表比较的已知失败仍保留。不能把这些教程示例通过计为所有输入、所有物理量或实际机组均已通过验证。

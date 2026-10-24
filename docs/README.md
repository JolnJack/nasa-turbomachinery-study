# 学习资料

你目前从零基础开始，建议按以下顺序阅读：

1. 先读[综合指南的 Fortran 入门和运行练习](tutorials/NASA叶轮机械FORTRAN程序完全解析与使用指南.md)，认识输入、赋值、循环和输出。
2. 阅读 [离心压气机零基础教程](tutorials/离心压气机程序_零基础全符号与概念详解.md)。
3. 阅读 [向心透平零基础教程](tutorials/向心透平程序_零基础全符号与概念详解.md)。
4. 配合 [NASA 原报告](../reports/README.md)、[综合指南的源码分段说明](tutorials/NASA叶轮机械FORTRAN程序完全解析与使用指南.md)和[修复版源码](../restored/README.md)，追踪一个变量的计算路径。
5. 用 [来源映射](../restored/SOURCE_MAP.md)、[勘误](../restored/ERRATA.md)、[单位与清单差异](CODE_CAVEATS.md)和[验证结果](../restored/SCAN_RESULTS.md)核对结论。

三份教程于 2026-10-24 完成本轮修订：纠正物理前提、单位、积分次数、参数继承和源码定位，补充运行练习与自检。早期原文移入 [originals/tutorials](../originals/tutorials/) 并保留原哈希。修订并不代表所有教学内容已穷尽审查或程序已完成科学验收。

特别注意：透平 SI 的 `N` 数值是 rev/s，`TOR/NS` 等派生字段仍有换算问题；本轮修订的是说明，未修改历史计算式。实际示例输出与核验范围见[本轮记录](../audit/tutorial-revision-2026-10-23/README.md)。

程序当前状态见 [STATUS.md](STATUS.md)。目录搬迁及原文件保护见 [ORGANIZATION.md](ORGANIZATION.md)。

# NASA 软件复原当前状态

更新：2026-10-23。**整体未最终验收。** 用户已授权实施，并选择以公式和程序清单为准、保留原表与勘误证据。

新增完整网格扫描、64位工程构建及独立逆设计搜索器；实际通过、拒绝、无输出及失败分类见 [SCAN_RESULTS.md](/Users/ikunsredemptionmac/Downloads/NASA/restored/SCAN_RESULTS.md)。旧搜索仍保留作对照，不能把新搜索结果称为旧算法完全相同。

当前修复版位于 [restored/README.md](/Users/ikunsredemptionmac/Downloads/NASA/restored/README.md)，验证报告位于 [VALIDATION.md](/Users/ikunsredemptionmac/Downloads/NASA/restored/VALIDATION.md)。根目录旧代码、可执行文件和Makefile仍是保留的原件，不代表修复版。

- 修复版已完成内存/输入/区间/扫描/标题等问题修复；61项功能检查通过，含新发现的逆设计失败后阻止无效状态沿用。
- 27位算术兼容版压气机470个参考打印值全部相同。
- 现代透平6模式可运行、完整堵塞扫描恢复、85点连续性与能量检查通过；其严格参考表检查仍失败。
- 新增历史后端：透平标准表原始值424/425相同，唯一差异为有公式矛盾证据的E1；按已选定的公式优先口径通过。运行 `make -C restored test-historical` 可复查，`make -C restored run-historical` 可运行设计内部系数继承示例。详见 [透平差异定位](/Users/ikunsredemptionmac/Downloads/NASA/restored/TURBINE_FINDINGS.md)。
- 原始14个文件和基线副本均经SHA-256核对一致。
- 新数据试跑：压气机6点、透平20工况完成，15项一致性检查通过；首次逆设计失败记录保留。详见 [新数据试运行](/Users/ikunsredemptionmac/Downloads/NASA/restored/NEW_DATA_TRIAL.md)。

不能宣称所有功能穷尽验证、无任何缺陷、全部实验曲线相同，或与未取得的NASA分发源文件逐字相同。

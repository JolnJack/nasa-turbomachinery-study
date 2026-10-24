# NASA 离心压气机与向心透平 FORTRAN 程序完全解析与实战指南

本指南对工作区中的两套经典 NASA 叶轮机械一维气动性能预测程序进行**逐行级源码拆解、物理公式映射与实战使用教学**：
1. **离心压气机变工况程序（NASA TN D-7487, 1973）**：[compressor_tn_d7487.f](file:///Users/ikunsredemptionmac/Downloads/NASA/compressor_tn_d7487.f)（原报告：[压气机程序 (Compressor Program).pdf](file:///Users/ikunsredemptionmac/Downloads/NASA/%E5%8E%8B%E6%B0%94%E6%9C%BA%E7%A8%8B%E5%BA%8F%20%28Compressor%20Program%29.pdf)）
2. **向心透平设计/变工况程序（NASA TN D-8063, 1975）**：[turbine_tn_d8063.f](file:///Users/ikunsredemptionmac/Downloads/NASA/turbine_tn_d8063.f)（原报告：[透平程序 (Turbine Program).pdf](file:///Users/ikunsredemptionmac/Downloads/NASA/%E9%80%8F%E5%B9%B3%E7%A8%8B%E5%BA%8F%20%28Turbine%20Program%29.pdf)）

---

## 一、 宏观全局视角：这两套程序是什么、解决什么问题？

在燃气轮机、涡轴发动机、航空辅助动力装置（APU）、涡轮增压器以及空间布雷顿循环发电系统中，**离心压气机（Centrifugal Compressor）**与**向心透平（Radial-Inflow Turbine）**是最核心的做功与增压部件。

这两套由 NASA Lewis 研究中心（现 Glenn 研究中心）开发的程序，是叶轮机械气动热力学领域的**经典一维平均流线法（1D Mean-Streamline Analysis）标杆代码**。它们解决的核心工程问题是：
* 在已知叶轮与扩压器/静叶的**宏观几何尺寸**（进出口直径、叶片角、叶高、喉部面积、叶片数等）和**进口工质状态**（总温、总压、比热比、气体常数、粘度）的前提下；
* 不需要耗时的三维 CFD 网格计算，在**几毫秒内**求解沿子午流道各关键截面的**速度三角形（Velocity Diagrams）**、**热力学状态参数（静温、静压、总温、总压、密度、马赫数）**以及**各项流动损失（冲角、摩擦、叶片载荷、回流、扩压等）**；
* 准确预测整机在不同转速下的**全工况特性图（Performance Map）**，并自动捕捉**喘振边界（Surge）**与**堵塞/极限载荷边界（Choke / Limiting Loading）**。

### 两套程序的核心设计思想对比

| 维度 | 离心压气机程序 ([compressor_tn_d7487.f](file:///Users/ikunsredemptionmac/Downloads/NASA/compressor_tn_d7487.f)) | 向心透平程序 ([turbine_tn_d8063.f](file:///Users/ikunsredemptionmac/Downloads/NASA/turbine_tn_d8063.f)) |
| :--- | :--- | :--- |
| **物理过程** | 叶轮对气体做功增压（逆压梯度流动，极易分离、失速与喘振） | 高温高压气体膨胀对转子做功（顺压梯度流动，易出现跨声速/超声速堵塞与后膨胀） |
| **计算模式** | **纯正算模式**：给定几何 + 转速 + 一组进口速度比 $(V/V_{\text{cr}})_0$，直接利用内置的 8 项经验损失关联式算出压比、效率及喘振/堵塞边界 | **双模式（先标定、后变工况）**：<br>1. **设计模式（`MODE=2/5`）**：输入设计点流量、压比、效率，用弦截法自动反算静叶总压比 `PD` 与转子损失系数 `XK`<br>2. **变工况模式（`MODE=0/1/3/4`）**：固定标定好的 `PD` 与 `XK`，扫描转速与静叶出口速度比 $(V/V_{\text{cr}})_1$ 算全特性图 |
| **单位制支持** | 仅国际单位制（SI：$\text{m}, \text{kg}, \text{s}, \text{K}, \text{N/m}^2$） | 支持国际单位制（SI，`MODE=0,1,2`）与美制工程单位（US Customary，`MODE=3,4,5`） |
| **边界处理亮点** | **双遍扫描法（Two-Pass Iteration）**：第一遍探明堵塞流量 $w_{\text{choke}}$，第二遍利用 $M_4$ 喘振准则剔除小于 $w_{\text{surge}}$ 的不稳定点 | **二分逼近堵塞 + 堵塞后超临界偏转**：用抛物线拟合精确捕捉转子堵塞点，并在堵塞后固定上游流量、自动偏转出口气流角 $\beta_4$ 直算到轴向声速极限载荷 $(W_x/W_{\text{cr}})_4 = 1.0$ |

---

## 二、 离心压气机程序（NASA TN D-7487）深度拆解

### 2.1 读懂源码的第一把钥匙：截面编号与变量名下标的“错位映射”

> [!IMPORTANT]
> **为什么直接对照报告看源码会觉得变量名下标对不上？**
> 作者 Michael R. Galvas 在编写 FORTRAN 源码时，最初将截面编号定义为：`0`（导叶前）、`1`（叶轮进口）、`2`（叶轮出口）、`3`（无叶扩压器出口）、`4`（有叶扩压器出口）。
> 但在撰写正式报告画图（Figure 1）时，为了细分诱导轮叶片前缘内外和有叶扩压器喉部，将报告正文和公式里的截面号改为了 `0 ~ 6`，**却没有修改 FORTRAN 源码中的变量名**！
> 掌握下面这张映射表，源码中所有变量名瞬间一目了然：

| 物理位置 | 报告正文/公式截面号 (Fig. 1) | FORTRAN 源码变量名中的代号 | 典型 FORTRAN 变量示例 |
| :--- | :---: | :---: | :--- |
| **进口导叶（IGV）上游** | **Station 0** | `0` | `POP` ($p'_0$), `TOP` ($T'_0$), `ROP` ($\rho'_0$), `MUO` ($\mu'_0$), `VOVCR` ($(V/V_{\text{cr}})_0$) |
| **诱导轮叶片前缘上游**（分轮毂 `H`、均方根 `MF`、叶尖 `T`） | **Station 1** | `1` (`1H`, `1MF`, `1T`) | `DIT` ($D_{1T}$), `D1H` ($D_{1H}$), `DMF` ($D_{1MF}$), `VM1H`, `VM1MF`, `VM1T`, `P1P` ($p'_{1MF}$), `T1` ($T_1$) |
| **诱导轮叶片前缘刚进入通道处**（冲角损失后） | **Station 2** | `IMF` / `1` | `PIPMF` ($p'_{2MF}$), `TOT1` ($T_2/T_1$) |
| **叶轮出口（Impeller Exit）** | **Station 3** | **`2`** | `D2` ($D_3$), `B2` ($b_3$), `B2X` ($\beta_{3b}$), `U2` ($u_3$), `VM2` ($V_{m3}$), `VU2` ($V_{u3}$), `W2` ($W_3$), `AL2` ($\alpha_3$), `T2` ($T_3$), `T2P` ($T'_3$), `P2` ($p_3$), `P2P` ($p'_3$), `RHO2` ($\rho_3$), `XM2` ($M_3$) |
| **无叶扩压器出口 / 有叶扩压器前缘** | **Station 4** | **`3`** / `NO=11` | `AL3` ($\alpha_4$, 有叶扩压器安装角), `P3P(NO)` ($p'_4$), `XMARR(NO)` ($M_4$) |
| **有叶扩压器喉部（Diffuser Throat）** | **Station 5** | **`TH`** | `ADTH` ($A_5$), `PTH` ($p_5$), `PTHP` ($p'_5$), `RTHP` ($\rho'_5$), `VCRTH` ($(V_{\text{cr}})_5$), `XMACH` ($M_5$) |
| **有叶扩压器出口（Diffuser Exit）** | **Station 6** | **`4`** / `EXIT` | `VOVCR4` ($(V/V_{\text{cr}})_6$), `PEXIT` ($p_6$), `PPEXIT` ($p'_6$), `P4PL`, `P4PG` |

---

### 2.2 压气机程序整体算法流程图

```mermaid
flowchart TD
    A["开始: 读取内置表 DATA<br/>(PREC1~5, CINC40~60, DIFLEM, FLRNG)"] --> B["标号 1: READ(5, INPUT)<br/>读取压气机几何、工质参数与 VOVCR 数组"]
    B --> C["打印输入参数表 (WRITE 309~320)<br/>角度转弧度, 计算临界声速 VCR 与叶尖速度 U1T"]
    C --> D["外层双遍循环: DO 18 L = 1, 2<br/>(L=1: 探测堵塞流量 WCHK; L=2: 正式计算并打印)"]
    D --> E["内层流量点循环: DO 17 J = MIN, NVOVCR<br/>给定进口轮毂临界速度比 VOVCR(J)"]
    
    E --> F{"是否有进口导叶预旋?<br/>AL1MF >= 0.001"}
    F -- "否 (无预旋)" --> G["径向平衡速度梯度积分 (Trapezoid + Simpson)<br/>求轮毂/RMS/叶尖子午速度与质量流量 SW"]
    F -- "是 (固壁涡预旋)" --> H["标号 9 循环: 递增 VOVCR1 匹配流量 SW<br/>计算导叶损失 DHIGV 及固壁涡速度分布"]
    
    G --> I["标号 36: 计算诱导轮进口速度三角形<br/>Stanitz 最佳冲角 BOPT 与冲角损失 DHINC"]
    H --> I
    
    I --> J["插值 Rodgers 曲线 (CINC40/50/60)<br/>判断诱导轮是否堵塞: INC <= CINC ?<br/>若堵塞则置 K = 1"]
    J --> K{"K=1 且 L=1 ?"}
    K -- "是 (第一遍找到诱导轮堵塞)" --> Z1["跳至标号 18: 记录 WCHK = EWF<br/>进入第二遍 L=2"]
    K -- "否" --> L["标号 4 迭代循环: 求解叶轮出口状态 (RHO2)<br/>计算滑移速度 VSL 与出口速度三角形"]
    
    L --> M["计算叶轮 5 项损失:<br/>叶片载荷 DHBL, 轮盘摩擦 DHDF,<br/>回流 DHRC, 表面摩擦 DHSF<br/>更新出口总压 P2P 与密度 R2G"]
    M --> N{"|RHO2 - R2G|/RHO2 > 0.001 ?"}
    N -- "是 (未收敛)" --> L
    N -- "否 (已收敛)" --> O["DO 1000 NO = 2, 11: 无叶扩压器 10 步积分<br/>二阶预测-校正法求解微分方程 (M, alpha, B)<br/>调用 FNTGRL 积分求总压比 TPL"]
    
    O --> P{"是否 L = 2 ?"}
    P -- "是" --> Q["由前缘马赫数 M4 插值 FLRNG 求喘振流量 WSURGE<br/>若 EWF < WSURGE 则打印小于喘振并跳下一流量点"]
    P -- "否" --> R["计算有叶扩压器喉部状态与流量函数 WFUNC"]
    Q --> R
    
    R --> S{"喉部是否堵塞?<br/>WFUNC >= FLFUNC"}
    S -- "是" --> T["置 CPSTAR = 0., K = 1 (扩压器堵塞)"]
    S -- "否" --> U["调用 LININT 双线性插值 PREC1~5<br/>并按面积比 AR 插值求最大静压恢复系数 CPSTAR"]
    
    T --> V["标号 14: 检查是否完成 L=1 堵塞探测<br/>计算有叶扩压器出口静压 PEXIT"]
    U --> V
    V --> W["标号 100 循环: 递增 VOVCR4 求解出口总压 PPEXIT<br/>计算扩压器损失 DHDIF、总压比 PR、总效率 ETAD<br/>及 8 项效率扣减值 DEIGV~DEVD"]
    W --> X{"L = 1 还是 L = 2 ?"}
    X -- "L = 1" --> E
    X -- "L = 2" --> Y["打印当前工况点性能与 8 项损失<br/>若 K=1 (已达堵塞点) 则完成本转速线, 跳回标号 1"]
    Z1 --> D
```

---

### 2.3 压气机源码逐段精讲（配合代码行号）

#### 第一段：内置经验数据库与输入定义（[L1–L36](file:///Users/ikunsredemptionmac/Downloads/NASA/compressor_tn_d7487.f#L1-L36)）
* **`PREC1` ~ `PREC5`（[L12–L26](file:///Users/ikunsredemptionmac/Downloads/NASA/compressor_tn_d7487.f#L12-L26)）**：有叶扩压器最大静压恢复系数 $C_p^{**}$ 的三维实验表（Runstadtler 实验数据）。
  * 第 1 维 `I=1..4` 对应喉部马赫数 `AMT` = $[0.2, 0.4, 0.6, 0.8]$；
  * 第 2 维 `J=1..6` 对应喉部气动堵塞度 `BARR` = $[0.02, 0.04, 0.06, 0.08, 0.10, 0.12]$；
  * `PREC1` 到 `PREC5` 分别对应面积比 $AR = A_6/A_5 = 1.2, 2.0, 3.0, 4.0, 5.0$。
* **`CINC60`, `CINC50`, `CINC40` 与 `MWRMS`（[L27–L30](file:///Users/ikunsredemptionmac/Downloads/NASA/compressor_tn_d7487.f#L27-L30)）**：诱导轮发生喉部堵塞时的极限冲角 $\beta_{1MF} - \beta_{1MFb}$（单位：度），横坐标是诱导轮均方根相对马赫数 `MWRMS` = $[0.5, 0.6, \dots, 1.2]$，分别对应叶片角 $60^\circ, 50^\circ, 40^\circ$。
* **`DIFLEM` 与 `FLRNG`（[L31–L32](file:///Users/ikunsredemptionmac/Downloads/NASA/compressor_tn_d7487.f#L31-L32)）**：有叶扩压器前缘马赫数 $M_4 \in [0.4, 1.0]$ 对应的压气机喘振与堵塞流量之比 $w_{\text{surge}}/w_{\text{choke}} \in [0.48, 0.89]$（对应报告图 2）。

#### 第二段：子午面进口速度分布与质量流量积分（[L61–L135](file:///Users/ikunsredemptionmac/Downloads/NASA/compressor_tn_d7487.f#L61-L135)）
1. **无预旋情况（`AL1MF < 0.001`，[L68–L100](file:///Users/ikunsredemptionmac/Downloads/NASA/compressor_tn_d7487.f#L68-L100)）**：
   * 输入的 `VOVCR(J)` 代表**诱导轮进口轮毂（Hub）处的临界速度比** $(V/V_{\text{cr}})_{1H}$，从而轮毂子午速度 `VM1H = VOVCR(J) * VCR`。
   * 考虑轮毂和叶尖的子午壁面曲率 `CURVH` ($C_{1H}$) 与 `CURVT` ($C_{1T}$)，由流线曲率径向平衡方程 $V_m = V_{m1H} \exp(\int C \, dn)$：
     * 用梯形法则求均方根直径 `DMF` 处的积分 `FINT` 和速度 `VM1MF`（[L83–L85](file:///Users/ikunsredemptionmac/Downloads/NASA/compressor_tn_d7487.f#L83-L85)，报告公式 B2）；
     * 用不等距三点 Simpson 法则求叶尖 `DIT` 处的积分 `GINT` 和速度 `VM1T`（[L86–L89](file:///Users/ikunsredemptionmac/Downloads/NASA/compressor_tn_d7487.f#L86-L89)，报告公式 B3）；
   * 投影到垂直于轴向的截面上（乘以壁面倾角余弦 $\cos\chi$，[L90–L92](file:///Users/ikunsredemptionmac/Downloads/NASA/compressor_tn_d7487.f#L90-L92)），算出三处静密度 `RHOH`, `RHOMF`, `RHOT`，再用**不等距 Simpson 公式**沿半径积分求出总质量流量 `SW`（[L96–L100](file:///Users/ikunsredemptionmac/Downloads/NASA/compressor_tn_d7487.f#L96-L100)，报告公式 B7）。
2. **有进口导叶固壁涡预旋情况（`AL1MF >= 0.001`，[L110–L135](file:///Users/ikunsredemptionmac/Downloads/NASA/compressor_tn_d7487.f#L110-L135)）**：
   * 先按报告公式 (B8)-(B9) 算出导叶安装角 `ALSTAG` 和动能损失系数 `ES` ($e_S$)。
   * 在标号 `9` 循环中，以 `0.001` 步长递增导叶后均方根速度比 `VOVCR1`，直到导叶后连续性算出的质量流量 `WTCHK` 等于 `SW`（[L113–L124](file:///Users/ikunsredemptionmac/Downloads/NASA/compressor_tn_d7487.f#L113-L124)）。
   * 固壁涡（Solid-body whirl）满足切向速度与半径成正比 $V_u = K_{Vu} r$，结合径向平衡方程得到 $V_{m1} = \sqrt{K_{Vm} - 2 V_{u1}^2}$（[L129–L134](file:///Users/ikunsredemptionmac/Downloads/NASA/compressor_tn_d7487.f#L129-L134)，报告公式 B20-B22），并算出**第 1 项损失：进口导叶损失 `DHIGV = ES * AKEID`**。

#### 第三段：诱导轮速度三角形、冲角损失与诱导轮堵塞判据（[L136–L192](file:///Users/ikunsredemptionmac/Downloads/NASA/compressor_tn_d7487.f#L136-L192)）
* 计算叶尖、轮毂、均方根半径（`1T`, `1H`, `1MF`）三处的绝对与相对速度三角形（[L136–L148](file:///Users/ikunsredemptionmac/Downloads/NASA/compressor_tn_d7487.f#L136-L148)）。
* **Stanitz 最佳冲角公式（[L150–L151](file:///Users/ikunsredemptionmac/Downloads/NASA/compressor_tn_d7487.f#L150-L151)）**：利用前缘叶片堵塞因子 `BLOCK` ($B_1$) 计算零攻角修正角 `EPS` ($\epsilon$)，得到最佳相对气流角 `BOPT = B1MF - EPS`（报告公式 B40-B42）。
* **第 2 项损失：诱导轮冲角损失 `DHINC`（[L157–L159](file:///Users/ikunsredemptionmac/Downloads/NASA/compressor_tn_d7487.f#L157-L159)）**：假设垂直于最佳气流角方向的相对速度分量 `WL = W1MF * SIN(ABS(BOPT - B1MF))` 完全耗散，故 `DHINC = WL**2 / 2.`，并按熵增公式算出进入诱导轮后的总压 `PIPMF`（报告公式 B43-B45）。
* **诱导轮喉部堵塞判据（[L164–L192](file:///Users/ikunsredemptionmac/Downloads/NASA/compressor_tn_d7487.f#L164-L192)）**：根据均方根相对马赫数 `RMRMS` 和叶片角 `B1MFB`，在 `CINC40/50/60` 表中做双线性插值得到极限堵塞冲角 `CINC`。若当前冲角 `INC <= CINC`，则置堵塞标志 **`K = 1`**！

#### 第四段：叶轮出口状态迭代与叶轮内 4 项损失（[L193–L255](file:///Users/ikunsredemptionmac/Downloads/NASA/compressor_tn_d7487.f#L193-L255)）
* **Wiesner 滑移速度 `VSL`（[L195–L198](file:///Users/ikunsredemptionmac/Downloads/NASA/compressor_tn_d7487.f#L195-L198)）**：计算叶轮出口滑移速度 $V_{\text{SL}} = u_3 \sqrt{\cos\beta_{3b}} / Z_3^{0.7}$，并在 $D_{1MF}/D_3 > \epsilon_{\lim}$ 时做三次方修正。
* **标号 `4` 密度迭代循环（[L202–L255](file:///Users/ikunsredemptionmac/Downloads/NASA/compressor_tn_d7487.f#L202-L255)）**：因为叶轮出口静密度 `RHO2` ($\rho_3$) 未知，先用估计值算出出口子午速度 `VM2`、切向绝对速度 `VU2`、相对速度 `W2`、静温 `T2` 和总温 `T2P`，然后计算叶轮的 4 项损失：
  1. **第 3 项损失：叶片载荷损失 `DHBL`（[L225–L229](file:///Users/ikunsredemptionmac/Downloads/NASA/compressor_tn_d7487.f#L225-L229)）**：先算叶轮扩散因子 `DF`（常规叶轮 `CONST1=0.75`，带分流叶片 `SPLT=1` 时 `CONST1=0.6`），再算 $\Delta h_{\text{BL}} = 0.05 D_f^2 u_3^2$（报告公式 B58-B59）。
  2. **第 4 项损失：轮盘摩擦损失 `DHDF`（[L231](file:///Users/ikunsredemptionmac/Downloads/NASA/compressor_tn_d7487.f#L231)）**：叶轮后盘风阻损失 $\Delta h_{\text{DF}} = 0.01356 \frac{\rho_3 u_3^3 D_3^2}{w \, \text{Re}^{0.2}}$（报告公式 B62）。
  3. **第 5 项损失：回流损失 `DHRC`（[L235](file:///Users/ikunsredemptionmac/Downloads/NASA/compressor_tn_d7487.f#L235)）**：气体从无叶扩压器倒流回叶轮造成的附加做功损失 $\Delta h_{\text{RC}} = 0.02 \sqrt{\tan\alpha_3} D_f^2 u_3^2$（报告公式 B73）。
  4. **第 6 项损失：表面摩擦损失 `DHSF`（[L236–L238](file:///Users/ikunsredemptionmac/Downloads/NASA/compressor_tn_d7487.f#L236-L238)）**：基于充分发展湍流管流公式，利用水力直径比 `DHYD`、流道长度比 `LOD` 和平均相对速度平方比 `WOU2` 计算 $\Delta h_{\text{SF}}$（常规叶轮系数 `5.6`，分流叶片叶轮系数 `7.0`，报告公式 B64-B67）。
* **极其重要的热力学关系（[L239–L245](file:///Users/ikunsredemptionmac/Downloads/NASA/compressor_tn_d7487.f#L239-L245)）**：
  * 轴输入总比功：`DHACT = DHAERO + DHDF + DHRC`（气动功 + 轮盘摩擦 + 回流损失）；
  * 叶轮通道等熵焓升：`HIS = DHAERO - DHBL - DHSF - DHIGV - DHINC`（仅扣除通道内部损失）；
  * 叶轮转子效率：`ETAR = HIS / DHAERO`，由此算出叶轮出口总压 `P2P`、静压 `P2` 和新密度 `R2G`，若 `|RHO2 - R2G|/RHO2 > 0.001` 则跳回标号 `4` 继续迭代！

#### 第五段：无叶扩压器 10 步微分方程积分与喘振边界判定（[L256–L327](file:///Users/ikunsredemptionmac/Downloads/NASA/compressor_tn_d7487.f#L256-L327)）
* 将无叶扩压器径向跨度从 $R = 1.0$ 到 `VLDRR` ($D_4/D_3$) 等分为 10 个区间、11 个站（`NO = 1..11`，步长 `DELTAR = (VLDRR - 1.) / 10.`）。
* 在 `DO 1000 NO=2,10` 循环中，采用**二阶预测-校正法（Heun's Method）**：
  * 先用当前站的参数计算弧长增量 `DS`、边界层位移厚度增量 `DELTAS`（平板 $1/7$ 次方湍流边界层公式 B80）、有效通道宽度比 `B`、马赫数平方增量 `VARM`（公式 B74）和流角正切增量 `VARAL`（公式 B75）；
  * 预测下一站的 `XM` 和 `ALPHA`，再算一次斜率并与第一次取算术平均（[L302–L304](file:///Users/ikunsredemptionmac/Downloads/NASA/compressor_tn_d7487.f#L302-L304)）；
  * 调用 [`SUBROUTINE FNTGRL`](file:///Users/ikunsredemptionmac/Downloads/NASA/compressor_tn_d7487.f#L466-L473) 对被积函数 $F = M^3 (a/a') (\rho/\rho') R$ 进行 Simpson 数值积分得到 `S(NO)`，代入公式 (B84) 算出总压比 `TPL` 和当前站总压 `P3P(NO)`。
* 循环结束后，`XMACH` 即为无叶扩压器出口（有叶扩压器前缘）马赫数 $M_4$，`PTHP` 为前缘总压 $p'_4$。
* **喘振点判定（[L320–L326](file:///Users/ikunsredemptionmac/Downloads/NASA/compressor_tn_d7487.f#L320-L326)）**：在第二遍扫描（`L=2`）时，利用 $M_4$ 在 `DIFLEM` / `FLRNG` 表中线性插值出流量范围比 `RANGE`，乘以第一遍探明的堵塞流量 `WCHK` 得到喘振流量 `WSURGE`。若当前折合流量 `EWF < WSURGE`，则跳至标号 `203` 打印 `WT FLOW LESS THAN SURGE FOR V/VCR=...` 并跳过该点！
* **第 7 项损失：无叶扩压器损失 `DHVLD`（[L329](file:///Users/ikunsredemptionmac/Downloads/NASA/compressor_tn_d7487.f#L329)）**：按报告公式 (B86) 由 $p'_3$ 与 $p'_4$ 的等熵温差算出。

#### 第六段：有叶扩压器计算、堵塞判据与结果输出（[L330–L411](file:///Users/ikunsredemptionmac/Downloads/NASA/compressor_tn_d7487.f#L330-L411)）
* **有叶扩压器前缘冲角投影（[L331–L332](file:///Users/ikunsredemptionmac/Downloads/NASA/compressor_tn_d7487.f#L331-L332)）**：将前缘马赫数投影到有叶扩压器安装角 `AL3` ($\alpha_4$) 方向：`XMACH = XMACH * COS(ABS(ALPHA - AL3))`，假定前缘到喉部静压 `PTH` 不变，重新算出喉部总压 `PTHP` ($p'_5$)。
* **有叶扩压器喉部堵塞判据（[L334–L337](file:///Users/ikunsredemptionmac/Downloads/NASA/compressor_tn_d7487.f#L334-L337)）**：计算喉部一维质量流量函数 `WFUNC` = $\frac{w \sqrt{T'_3}}{p'_5 A_5 B_5}$，若达到或超过声速极限值 `FLFUNC`（报告第12页公式），则扩压器喉部堵塞：置 **`K = 1`**，且令静压恢复系数 **`CPSTAR = 0.`**（模拟堵塞点垂直下降的压比特性线）。
* **最大静压恢复系数 `CPSTAR` 插值（[L338–L357](file:///Users/ikunsredemptionmac/Downloads/NASA/compressor_tn_d7487.f#L338-L357)）**：根据面积比 `AR` 落在哪个区间（$[1.2, 2.0], [2.0, 3.0], [3.0, 4.0], [4.0, 5.0]$），调用两次 [`SUBROUTINE LININT`](file:///Users/ikunsredemptionmac/Downloads/NASA/compressor_tn_d7487.f#L448-L465) 对喉部马赫数 `XMACH` 和喉部堵塞度 `BT = 1. - B` 做二维双线性插值，再按 `AR` 线性插值得到 `CPSTAR`，算出扩压器出口静压 `PEXIT = CPSTAR * (PTHP - PTH) + PTH`。
* **扩压器出口总压 `PPEXIT` 迭代（[L365–L371](file:///Users/ikunsredemptionmac/Downloads/NASA/compressor_tn_d7487.f#L365-L371)）**：在标号 `100` 循环中，从 `.020` 开始以步长 `.001` 递增出口临界速度比 `VOVCR4` ($(V/V_{\text{cr}})_6$)，直到由静压算出的总压下界 `P4PL`（公式 B88）追上由连续性算出的总压上界 `P4PG`（公式 B89），定出出口总压 `PPEXIT` ($p'_6$)。
* **第 8 项损失：有叶扩压器损失 `DHDIF` 与整机性能汇总（[L372–L382](file:///Users/ikunsredemptionmac/Downloads/NASA/compressor_tn_d7487.f#L372-L382)）**：算出 `DHDIF` ($\Delta h_{\text{VD}}$)、整机总压比 `PR = PPEXIT / POP`、整机总绝热效率 `ETAD` 以及 8 项损失各自的效率扣减比例（$\Delta\eta_i = \Delta h_i / \Delta h_{\text{act}}$）。

---

## 三、 向心透平程序（NASA TN D-8063）深度拆解

### 3.1 气动截面编号（Stations 0–5）与物理图景

透平程序的截面编号在报告（Figure 1 & Figure 5）与 FORTRAN 源码中**完全一致**：
* **Station 0**：透平蜗壳进口（Scroll Inlet，面积 `A0`，总压 `P0` $p'_0$，总温 `T0` $T'_0$）
* **Station 1**：静叶（Stator）尾缘**内侧**（叶片通道刚结束处，面积 `A1`，气流角 `AL1` $\alpha_1$，总压 $p'_1 = \text{PD} \cdot p'_0$）
* **Station 2**：静叶尾缘**外侧**（经历尾缘厚度突然扩张后，面积 $A_2 = A_1 / \text{BL1}$，直径 `D2`）
* **Station 3**：转子（Rotor）进口前缘**外侧**（历经无叶自由涡空间 $D_2 \to D_3$ 后，面积 `A3`，直径 `D3`，轮缘线速度 `U3`）
* **Station 4**：转子尾缘**内侧**（转子通道刚结束处，面积 $A_4 = \text{BL4} \cdot A_5$，相对气流角 `B4` $\beta_4$）
* **Station 5**：转子尾缘**外侧**（透平出口，面积 `A5`，平均轮缘速度比 `U4U3` = $U_4/U_3$）

---

### 3.2 透平程序整体算法流程图

```mermaid
flowchart TD
    A["开始: 定义一维等熵流量语句函数 SUBR(X,G)"] --> B["标号 1: 读取两行标题卡 NAME, CASE<br/>及 NAMELIST /IN/ 输入参数"]
    B --> C["根据 MODE 判断单位制:<br/>MODE=0,1,2 为 SI 制; MODE=3,4,5 为美制英尺磅<br/>计算进口临界声速 VCR 与 PVCR"]
    C --> D{"运行模式判断:<br/>设计模式 (MODE=2,5)<br/>还是变工况模式 (MODE=0,1,3,4) ?"}
    
    D -- "设计模式 (MODE=2,5)" --> E["初始化 PD=1.0, K=1<br/>标号 5 牛顿迭代: 由设计流量 WD 反解 V1VC1"]
    D -- "变工况模式 (MODE=0,1,3,4)" --> F{"静叶是否超临界?<br/>V1VC1 > 1.0"}
    F -- "是 (静叶已堵塞)" --> G["标号 15: 锁定静叶声速堵塞流量 WK<br/>后膨胀反算新静叶出口角 AL1"]
    F -- "否" --> H["标号 10: 计算流量 W1<br/>标号 12 牛顿迭代求进口速度比 V0VC0"]
    E --> H
    G --> I["标号 13 & 61 牛顿迭代:<br/>考虑尾缘堵塞 BL1 求静叶出口外侧 (Station 2) 状态"]
    H --> I
    
    I --> J["标号 22 牛顿迭代: 无叶间隙自由涡守恒<br/>求转子进口 (Station 3) 绝对与相对速度三角形"]
    J --> K["Stanitz 滑移公式求最佳进口相对流角 AB<br/>冲角 XI3 = B3 - AB (负冲角指数2, 正冲角指数3)"]
    K --> L["标号 31 & 32 循环: 转子出口求解<br/>计算转子损失项 CX, AX, BX, EX 与流量参数 YCAL<br/>调用 CONTIN + PABC 抛物线拟合法更新 Y = (W/Wcr)4"]
    
    L --> M{"CONTIN 返回状态 IND?"}
    M -- "IND < 10 (未收敛)" --> L
    M -- "IND = 10 (转子发生堵塞!)" --> N["标号 33~34: 回退 V1VC1 并折半步长 DELV = DELV/2<br/>置 N=2 二分逼近精确转子堵塞点"]
    N --> F
    M -- "IND >= 6 且收敛 (标号 80)" --> O{"是否处于二分逼近转子堵塞过程中?<br/>(非设计模式且 N=2)"}
    O -- "是且未达精度 TOL" --> N
    O -- "已达精度 TOL" --> P["标号 35: 置 IT=2 (标记已找到转子堵塞点)"]
    O -- "正常未堵塞点 (N=1)" --> Q["标号 82 & 85: 计算转子出口分量 WUWC4, WXWC4"]
    P --> Q
    
    Q --> R{"转子出口轴向相对速度是否超声速?<br/>HA = WXWC4 > 1.0"}
    R -- "是 (超过极限载荷)" --> S["标号 56~58: 缩小步长 DELL=DELY/5 及对折<br/>逼近 WXWC4 = 1.0 极限载荷点"]
    R -- "否" --> T["标号 70 牛顿迭代: 考虑转子尾缘堵塞 BL4<br/>求透平出口外侧 (Station 5) 速度三角形与总/静压比、效率"]
    
    T --> U{"是否为设计模式?<br/>(MODE=2,5)"}
    U -- "是: 自动标定 XK 和 PD" --> V["先调用 GETK (K=1..5) 弦截法迭代 XK 匹配设计效率 ETAD;<br/>再调用 SEEKPR (L=1..5) 弦截法迭代 PD 匹配设计压比 PDSGN"]
    V -- "未收敛" --> E
    V -- "XK 与 PD 均收敛" --> W["标号 40: 计算折合性能参数与比转速 XNS<br/>打印输出结果 (WRITE 500~526)"]
    U -- "否 (变工况模式)" --> W
    
    W --> X{"下一步推进方式?"}
    X -- "设计模式完成" --> B
    X -- "常规变工况 (IT=1)" --> Y["V1VC1 = V1VC1 + DELV<br/>若 V1VC1 <= VMAX 则继续下一工况点"]
    Y --> F
    X -- "转子堵塞后超临界膨胀 (IT>=2)" --> Z["标号 55 & 53: 冻结转子进口条件<br/>递增 Y = Y + DELY, 反算偏转后的出口角 B4<br/>直至 WXWC4 达 1.0 打印 LIMITING LOADING"]
    Z --> Q
    S --> Z
```

---

### 3.3 透平源码逐段精讲（配合代码行号）

#### 第一段：核心一维可压缩流函数 `SUBR(X,G)`（[L17](file:///Users/ikunsredemptionmac/Downloads/NASA/turbine_tn_d8063.f#L17)）
在阅读透平源码时，你会看到到处都在调用 `SUBR(X, G)`。它是第 17 行定义的 FORTRAN 语句函数（Statement Function）：
```fortran
SUBR(X,G)=(1.-(G-1.)/(G+1.)*X*X)**(1./(G-1.))*X
```
它的物理意义就是报告公式 (B1) 的**无量纲单位面积质量流量（密流函数）**：
$$\text{SUBR}\!\left(\frac{V}{V_{\text{cr}}}, \gamma\right) = \frac{\rho V}{\rho' V_{\text{cr}}} = \frac{V}{V_{\text{cr}}} \left[ 1 - \frac{\gamma - 1}{\gamma + 1} \left(\frac{V}{V_{\text{cr}}}\right)^2 \right]^{\frac{1}{\gamma - 1}}$$
当临界速度比 $X = V/V_{\text{cr}} = 1.0$（声速）时，`SUBR(1.0, G)` 取得最大值，对应声速喉部堵塞！

#### 第二段：静叶分析与尾缘堵塞（[L48–L144](file:///Users/ikunsredemptionmac/Downloads/NASA/turbine_tn_d8063.f#L48-L144)）
1. **设计模式反解 `V1VC1`（[L61–L70](file:///Users/ikunsredemptionmac/Downloads/NASA/turbine_tn_d8063.f#L61-L70)）**：
   * 在设计模式下，质量流量 `WD` 是已知的输入，因此通过牛顿-拉夫逊（Newton-Raphson）迭代法（标号 `5` 循环：`V1VC1 = X - F/FP`）求解 $\text{SUBR}(X, \gamma) = \frac{w_{\text{des}}}{(\rho' V_{\text{cr}})_0 A_1 \cos\alpha_1 \cdot \text{PD}}$，反算出设计点的静叶出口临界速度比 `V1VC1`。
2. **变工况静叶超临界后膨胀（[L71–L79](file:///Users/ikunsredemptionmac/Downloads/NASA/turbine_tn_d8063.f#L71-L79)，标号 `15`）**：
   * 当变工况扫描到 `V1VC1 > 1.0` 时，静叶已在 `VK = 1.0` 处发生声速堵塞，最大质量流量锁定为 `WK = COS(ALX*T)*PVK*A1*PVCR*PD`。
   * 超声速气流在静叶斜切口下游发生普朗特-迈耶自由膨胀，程序根据连续性方程反算出气流自动偏转后的新静叶出口角 `AL1 = ACOS(COSAL1)`（报告公式 B4a）。
3. **静叶尾缘突扩（Station 1 $\to$ 2，[L93–L113](file:///Users/ikunsredemptionmac/Downloads/NASA/turbine_tn_d8063.f#L93-L113)）与无叶间隙（Station 2 $\to$ 3，[L114–L131](file:///Users/ikunsredemptionmac/Downloads/NASA/turbine_tn_d8063.f#L114-L131)）**：
   * 分别用两个牛顿迭代循环（标号 `61` 和标号 `22`），在切向速度守恒（$V_{u2} = V_{u1}$，以及自由涡 $V_{u3} = V_{u2} D_2 / D_3$）下，求解径向速度比 `VRVC2` 和 `VRVC3`（报告公式 B5a-B6e）。

#### 第三段：转子进口冲角模型与转子出口抛物线求解器 `CONTIN`（[L132–L218](file:///Users/ikunsredemptionmac/Downloads/NASA/turbine_tn_d8063.f#L132-L218)）
* **Stanitz 最佳进口流角与不对称冲角损失模型（[L149–L174](file:///Users/ikunsredemptionmac/Downloads/NASA/turbine_tn_d8063.f#L149-L174)）**：
  * 由转子叶片数 `ZZ` 计算滑移系数 `V3TU3 = 1. - 1.98/ZZ`（报告公式 B8a），求出最佳进口相对气流角 `AB` ($\varphi$) 和冲角 `XI3 = B3 - AB` ($i_3 = \beta_3 - \varphi$)。
  * 在标号 `32` 循环（[L169–L170](file:///Users/ikunsredemptionmac/Downloads/NASA/turbine_tn_d8063.f#L169-L170)）中：
    ```fortran
    CX=W3WC4**2*(XK*FC**2+FS**2)
    IF(B3.GT.AB) CX=W3WC4**2*(XK*FC**2+FS**3)
    ```
    这里完美体现了报告公式 (3a) 和 (B12) 的改进：当负冲角（`B3 <= AB`）时，冲角损失按 $\sin^2 i_3$（`FS**2`）计算；当正冲角（`B3 > AB`）时，冲角损失按 $\sin^3 i_3$（`FS**3`）计算！同时转子内部粘性损失只取沿最佳流角方向的速度分量 $W_3 \cos i_3$（`XK * FC**2`）。
* **转子出口连续性迭代与堵塞捕捉（[L171–L206](file:///Users/ikunsredemptionmac/Downloads/NASA/turbine_tn_d8063.f#L171-L206)）**：
  * 转子出口既受相对总压恢复系数 `EX` ($p''_4/p''_{4,\text{id}}$，本身依赖于未知的出口速度比 `Y` = $(W/W_{\text{cr}})_4$) 影响，又受可压缩密流函数 `SUBR(Y, G)` 影响。
  * 主程序调用 [`SUBROUTINE CONTIN`](file:///Users/ikunsredemptionmac/Downloads/NASA/turbine_tn_d8063.f#L473-L575)，以步长 `XDEL = 0.1` 选取三个试探点 `X(1), X(2), X(3)`，调用 [`SUBROUTINE PABC`](file:///Users/ikunsredemptionmac/Downloads/NASA/turbine_tn_d8063.f#L576-L588) 拟合二次抛物线 $y = A x^2 + B x + C$ 来求解满足 `YCAL = YGIV` 的亚声速根。
  * 如果给定静叶出口速度比 `V1VC1` 太大，导致转子出口即使达到最大密流（抛物线判别式 `DISCR < 0.` 且顶点处 `YCALC < YGIV`）也通不过上游来的流量，`CONTIN` 就会返回 **`IND = 10`（转子堵塞！）**。
  * 主程序收到 `IND = 10` 后跳到标号 `33–34`，回退 `V1VC1` 并将步长折半 `DELV = DELV / 2.`，用二分法逼近使转子刚好达到声速堵塞的临界 `V1VC1` 值（精度 `TOL = 0.00001`），然后令 `IT = 2` 进入转子堵塞后状态！

#### 第四段：设计参数自动标定（`GETK` 与 `SEEKPR`）及极限载荷计算（[L251–L379](file:///Users/ikunsredemptionmac/Downloads/NASA/turbine_tn_d8063.f#L251-L379)）
* **设计模式双层弦截法反算（[L253–L266](file:///Users/ikunsredemptionmac/Downloads/NASA/turbine_tn_d8063.f#L253-L266)）**：
  1. 内层先调 [`SUBROUTINE GETK`](file:///Users/ikunsredemptionmac/Downloads/NASA/turbine_tn_d8063.f#L431-L451)：以 `0.005` 步长递增 `XK`，一旦发现误差 `DIF2 * DIF1 < 0`（跨过零点），立即用弦截法（False Positioning：`XK = -(XK2-XK1)/(DIF2-DIF1)*DIF1 + XK1`）一步算出精确的 `XK` 并置 `K = 5`；
  2. 外层再调 [`SUBROUTINE SEEKPR`](file:///Users/ikunsredemptionmac/Downloads/NASA/turbine_tn_d8063.f#L452-L472)：以 `-0.005` 步长递减 `PD`，一旦跨过设计压比 `PDSGN`，用弦截法算出新的 `PD` 并跳回标号 `4` 重新触发内层 `GETK` 迭代，直至 `PD` 和 `XK` 同时满足设计压比与设计效率！
* **转子堵塞后的后膨胀与极限载荷（[L350–L378](file:///Users/ikunsredemptionmac/Downloads/NASA/turbine_tn_d8063.f#L350-L378)，标号 `55–59`）**：
  * 当转子已经堵塞（`IT >= 2`）后，透平质量流量不再增加，上游（Station 0~3）的所有参数完全固定。
  * 在标号 `55` 中，程序以 `DELY`（如 `0.05`）为步长直接增加转子出口相对临界速度比 `Y` ($(W/W_{\text{cr}})_4 > 1.0$)，并在标号 `53` 根据连续性方程反算气流在转子尾缘斜切口膨胀偏转后的新相对气流角 `B4`（报告公式 B13a）。
  * 当转子出口轴向相对速度比 `HA = WXWC4` 达到或超过 `1.0`（即轴向流动也达到声速，无法再通过压降进一步加速，称为**叶片极限载荷 Limiting Loading**）时，程序跳至标号 `56–59`，将步长缩小为 `DELL = DELY / 5.` 并不断折半，精确停在 `WXWC4 ≈ 1.0`（误差 `< 2%`）处，打印 `LAST CASE IS APPROXIMATE LIMITING LOADING`！

---

## 四、 实战使用手册：怎么运行、怎么改参数、怎么看结果？

### 4.1 一键编译命令

在终端进入 `/Users/ikunsredemptionmac/Downloads/NASA` 目录，执行以下命令编译：

```bash
# 编译压气机程序
/opt/homebrew/bin/gfortran -std=legacy -fno-automatic -w compressor_tn_d7487.f -o compressor_tn_d7487

# 编译透平程序
/opt/homebrew/bin/gfortran -std=legacy -fno-automatic -w turbine_tn_d8063.f -o turbine_tn_d8063
```
> [!TIP]
> 为什么要加 `-fno-automatic`？因为 1970 年代的 IBM 7094 FORTRAN IV 默认所有子程序局部变量都是静态分配的（即第二次进入 `SUBROUTINE GETK`、`SEEKPR` 或 `CONTIN` 时，上次算出的局部变量 `XK1`, `DIF1`, `PD1`, `XORIG`, `NCALL` 仍然保留在内存中）。加上 `-fno-automatic` 即可完美复现 1970 年代大型机的静态内存行为；也可直接运行 `make` 编译、`make run` 运行全部标准算例。

---

### 4.2 如何使用离心压气机程序（`compressor_tn_d7487`）

#### （1）准备输入文件（参考 [compressor_tn_d7487.inp](file:///Users/ikunsredemptionmac/Downloads/NASA/compressor_tn_d7487.inp)）
输入采用 FORTRAN `NAMELIST /INPUT/` 格式，每个 `&INPUT ... &END` 块代表**一条转速线**的计算任务：

```fortran
 &INPUT
 ! --- 1. 工质与进口总参数 ---
 GAM=1.4,          ! 比热比 gamma
 RGAS=287.05,      ! 气体常数 R, J/(kg*K)
 POP=101325.,      ! 进口总压 p0', N/m^2 (Pa)
 TOP=288.15,       ! 进口总温 T0', K
 MUO=1.788E-5,     ! 进口总温下的动力粘度 mu0', N*s/m^2

 ! --- 2. 转速与壁面摩擦系数 ---
 N=72000.,         ! 设计转速 N_DES, rpm
 NONDES=1.0,       ! 当前计算的折合转速比 N / N_DES (1.0 代表 100% 转速)
 CF=.004,          ! 湿润壁面摩擦系数 Cf (通常取 0.004 ~ 0.005)

 ! --- 3. 诱导轮 (Inducer) 进口几何 ---
 DIT=.0813,        ! 诱导轮进口叶尖直径 D1T, m
 LAMX=.5313,       ! 诱导轮进口轮毂比 (轮毂直径/叶尖直径) lambda = D1H / D1T
 B1MFB=49.,        ! 诱导轮进口均方根半径处叶片角 beta_1MFb, 度 (相对子午面，必须在 40~60 度之间)
 BLOCK=.9,         ! 诱导轮进口均方根处叶片堵塞因子 B1 = 1 - Z1*tu/(2*pi*r1MF)
 AL1MF=0.,         ! 进口导叶在均方根半径处的固壁涡预旋角 alpha_1MF, 度 (0 代表无导叶/无预旋)
 CHIH=7.,          ! 诱导轮进口轮毂子午壁面倾角 chi_1H, 度 (有导叶时必须设为 0)
 CHIT=0.,          ! 诱导轮进口叶尖子午壁面倾角 chi_1T, 度 (有导叶时必须设为 0)
 CURVH=0.,         ! 诱导轮进口轮毂子午壁面曲率 C1H, m^-1 (有导叶时必须设为 0)
 CURVT=0.,         ! 诱导轮进口叶尖子午壁面曲率 C1T, m^-1 (有导叶时必须设为 0)

 ! --- 4. 叶轮出口 (Impeller Exit) 几何 ---
 DRAT=.5614,       ! 诱导轮进口叶尖直径与叶轮出口直径之比 D1T / D3
 Z=32.,            ! 叶轮出口总叶片数 Z3 (含分流叶片)
 B2=.0051,         ! 叶轮出口叶高 b3, m
 B2X=25.,          ! 叶轮出口叶片后弯角 beta_3b, 度 (径向直叶片为 0，后弯为正)
 SPLT=1,           ! 分流叶片控制开关: 0 = 无分流叶片(常规叶轮), 1 = 带半长分流叶片(Splitter)

 ! --- 5. 无叶与有叶扩压器 (Diffuser) 几何 ---
 VLDRR=1.14,       ! 无叶扩压器出口与进口直径比 D4 / D3
 AL3=78.,          ! 有叶扩压器前缘叶片安装角 alpha_4, 度 (相对子午面)
 ADTH=.00071,      ! 有叶扩压器所有通道的总喉部面积 A5, m^2
 AR=2.7,           ! 有叶扩压器出口与喉部面积比 A6 / A5 (必须在 1.2 ~ 5.0 之间)

 ! --- 6. 扫描的进口临界速度比数组 ---
 NVOVCR=15,        ! VOVCR 数组的元素个数 (最多 15 个)
 VOVCR=.47,.48,.49,.5,.51,.52,.53,.54,.55,.56,.57,.58,.59,.6,.61
 &END
```

#### （2）使用压气机程序的 3 个关键注意事项
1. **连续跑多条转速线时**：因为源码第 52–56 行直接把变量 `B2X`, `AL3`, `AL1MF`, `CHIH`, `CHIT` 乘以 `0.01745` 转成了弧度覆盖原变量，所以在同一个 `.inp` 文件里写第 2、3、4 条转速线时，**必须完整写出所有参数**（如 [compressor_tn_d7487.inp](file:///Users/ikunsredemptionmac/Downloads/NASA/compressor_tn_d7487.inp) 所示），不能只写 `NONDES` 和 `VOVCR`。
2. **如何合理设置 `VOVCR` 数组？**
   * `VOVCR` 必须**从小到大排列**，且间隔尽可能均匀（推荐步长 `0.01`），最后一个点必须足以让压气机达到堵塞（Choke），而第一个点不能已经超过堵塞流量。
   * 如果报错 `COMPRESSOR CHOKING FLOW HAS NOT BEEN REACHED`：说明 `VOVCR` 最大值设小了，还没算到堵塞点，需调大 `VOVCR` 的上限。
   * 如果报错 `VOVCR ARRAY TOO LARGE`：说明第一个 `VOVCR(1)` 就已经发生堵塞了，需调小 `VOVCR` 的起始值。
   * 如果报错 `IRRATIONAL EXIT TRIANGLE`：说明 `VOVCR` 设得太小，导致叶轮出口切向速度或子午速度算出负值，需适当调大起始值。
3. **输出结果怎么看？**
   * `SURGE FLOW RATE` / `CHOKE FLOW RATE`：当前转速下预测的喘振折合流量与堵塞折合流量（$\text{kg/s}$）。
   * 每个工况点打印两行核心数据：
     * 第一行：`WEQ`（折合流量 $w\sqrt{\theta}/\delta$, $\text{kg/s}$）、`PRESSURE RATIO`（整机总压比 $p'_6/p'_0$）、`ETAT`（整机总对总绝热效率 $\eta_{\text{AD}}$）。
     * 第二行：8 项损失各自吃掉了多少效率（`DETAIGV` 导叶、`DETAINC` 冲角、`DETABL` 叶片载荷、`DETASF` 表面摩擦、`DETADF` 轮盘摩擦、`DETARC` 回流、`DETAVLD` 无叶扩压器、`DETAVD` 有叶扩压器）。

---

### 4.3 如何使用向心透平程序（`turbine_tn_d8063`）

#### （1）两步走标准工作流（参考 [turbine_tn_d8063.inp](file:///Users/ikunsredemptionmac/Downloads/NASA/turbine_tn_d8063.inp)）
透平程序每个算例的前两行**必须是标题行**（每行最多 60 字符），随后是 `&IN ... &END` 块：

* **第一步：用设计模式（`MODE=2`）标定损失参数 `PD` 和 `XK`**
  ```fortran
              12.62-CM DIA TURBINE
              100 PERCENT SPEED
   &IN
   MODE=2,           ! 2 = SI 单位制设计模式 (5 = 美制设计模式)
   ITEST=2,          ! 2 = 匹配总效率 ETAD 与总-总压比 PDSGN (1 = 匹配静效率与总-静压比)
   ETAD=.913,        ! 设计点目标效率 (0.913)
   PDSGN=1.74,       ! 设计点目标压比 (p0'/p5' = 1.74)
   WD=.33879,        ! 设计点质量流量 w, kg/s
   G=1.6667,         ! 比热比 gamma (此处为氩气/氦氙混合气 1.6667，空气填 1.4)
   R=99.1976,        ! 气体常数 R, J/(kg*K)
   P0=172368.9,      ! 进口总压 p0', Pa
   T0=1144.44,       ! 进口总温 T0', K
   A0=.0120176,      ! 蜗壳进口面积 A0, m^2
   A1=.0038008,      ! 静叶出口内侧面积 A1, m^2
   A3=.0039789,      ! 转子进口外侧面积 A3, m^2
   A5=.0044543,      ! 转子出口外侧面积 A5, m^2
   D2=12.9997,       ! 静叶出口直径 D2, cm (注意单位是厘米!)
   D3=12.6238,       ! 转子进口直径 D3, cm (注意单位是厘米!)
   AL1=72.47,        ! 静叶出口叶片角 alpha_1, 度
   B4=-56.86,        ! 转子出口叶片角 beta_4, 度 (反向旋转方向为负!)
   BL1=.95168,       ! 静叶尾缘堵塞因子 B1 (通道内面积/通道外面积)
   BL4=.93718,       ! 转子尾缘堵塞因子 B4 (通道内面积/通道外面积)
   ZZ=22.,           ! 转子进口叶片数 ZZ
   U3=237.9524,      ! 转子进口叶尖线速度 U3, m/s
   U4U3=.567765,     ! 转子出口平均半径与进口半径之比 U4 / U3
   V1=.30, DELV=.05, VMAX=.80, DELY=.05, YMAX=1.40
   &END
  ```
  运行后，程序会在头部打印标定出的两个关键参数：
  ```text
               PD   0.987837
                K   0.286839
  ```

* **第二步：将标定出的 `PD` 和 `XK` 填入变工况模式（`MODE=0` 长输出 或 `MODE=1` 短输出）**
  * 在同一个输入文件中，后续变工况算例只需要修改变化的参数（如只改转速 `U3`），其余参数会自动继承上一个算例的值（注意：若在現代 IEEE 754 浮点数下希望 `V1=.30` 按 `.05` 累加包含 `.80` 边界点，可将 `VMAX` 设为 `.8001`）：
  ```fortran
              12.62-CM DIA TURBINE
              100 PERCENT SPEED
   &IN MODE=1, XK=.28699, PD=.98783, VMAX=.8001 &END
              12.62-CM DIA TURBINE
              110 PERCENT SPEED
   &IN U3=261.7476 &END
              12.62-CM DIA TURBINE
              90 PERCENT SPEED
   &IN U3=214.1572 &END
  ```

#### （2）透平输出结果怎么看？
* **长输出（`MODE=0` 或 `2`）**分为上下两大块：
  1. `VELOCITIES AND ANGLES`：完整列出从 Station 0 到 Station 5 的所有绝对临界速度比（`V/VCR`）、切向/径向/轴向分量（`VU/VCR`, `VR/VCR`, `VX/VCR`）、相对临界速度比（`W/WCR`）、气流角（`ALPHA-1,2,3,5`, `BETA-3,4,5`）、转子进口冲角 `I-3` ($i_3$) 以及临界声速 `VCR)3`, `VCR)5`。
  2. `OVERALL PERFORMANCE`：
     * 左列（海平面标准空气折合参数）：`EQ-W`（折合流量）、`EQ-DEL-H`（折合比功）、`EQ-N`（折合转速）、`EQ-TOR`（折合扭矩）、`N`（实际转速，SI 制下为 $\text{rad/s}$）；
     * 中左列：`EQ-P0,/P5`（折合总-静压比）、`ETA-S`（总-静效率 $\eta_s$）、`ETA-T`（总-总效率 $\eta_t$）、`EQ-P0,/P5,`（折合总-总压比）、`P`（输出功率，$\text{kW}$）；
     * 中列：`P0,/P5`（实际总-静压比 $p'_0/p_5$）、`NU`（速比 $\nu = U_3 / \sqrt{2 \Delta h'_{\text{id},s}}$）、`NS`（比转速 $N_s$）、`P0,/P5,`（实际总-总压比 $p'_0/p'_5$）、`WN/DEL`（质量流量转速参数）；
     * 右两列：实际流量 `W` ($\text{kg/s}$)、实际比功 `DEL-H` ($\text{J/kg}$)、功系数 `W.F.` ($\Delta h'/U_3^2$)、扭矩 `TOR` ($\text{N}\cdot\text{m}$)、出口总温 `T5,` ($\text{K}$)、出口总压 `P5,` ($\text{Pa}$)。
* **短输出（`MODE=1` 或 `4`）**：直接输出一张紧凑的 10 列性能表（包含 `V1VC1`, `NS`, `EQ-P5/P0,`, `NU`, `ETAT`, `ETAS`, `DHTCR`, `WTHODE`, `EQ-P0,/P5`, `EQ-P0,/P5,`），非常适合直接导入 Python / MATLAB / Excel 绘制透平特性曲线图！

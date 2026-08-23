---
name: hardware-tools
overview: 为"工作助手"新增 7 个硬件工程师计算/速查工具，按"聚合页"组织：新增"🔧 硬件工具箱"栏目（DC-DC BUCK、散热功耗、分压偏置驱动、晶振匹配、PCB 走线、电池续航、波特率定时器共 7 个计算器 Tab），并把"常识查询"栏改造为速查合集页（色环电阻+单位换算+E系列+接口引脚+封装尺寸+AWG 线规），风格沿用功率变换页的实时计算+卡片式 UI。
design:
  styleKeywords:
    - macOS 风格
    - 浅灰底白色卡片
    - accent 蓝强调
    - 圆角细边框
    - Tab 聚合页
    - 实时计算
  fontSystem:
    fontFamily: Microsoft YaHei UI
    heading:
      size: 22px
      weight: 700
    subheading:
      size: 14px
      weight: 600
    body:
      size: 12px
      weight: 400
  colorSystem:
    primary:
      - "#007AFF"
      - "#409EFF"
    background:
      - "#F2F3F5"
      - "#FFFFFF"
      - "#F5F7FA"
    text:
      - "#1D1D1F"
      - "#6E6E73"
      - "#FFFFFF"
    functional:
      - "#67C23A"
      - "#E6A23C"
      - "#F56C6C"
      - "#E5E5EA"
todos:
  - id: create-buck-thermal-tabs
    content: 新建硬件工具箱页：实现 DC-DC BUCK 与散热功耗两个计算 Tab 及器件库
    status: completed
  - id: create-bias-crystal-pcb-tabs
    content: 补充分压偏置驱动、晶振匹配、PCB 走线三个计算 Tab
    status: completed
    dependencies:
      - create-buck-thermal-tabs
  - id: create-battery-baud-tabs
    content: 补充电池续航、波特率定时器两个 Tab，完成 7 个计算工具
    status: completed
    dependencies:
      - create-bias-crystal-pcb-tabs
  - id: create-reference-lookup-page
    content: 新建常识速查合集页：复用色环电阻页并实现单位换算/E系列/接口/封装/AWG 五个速查 Tab
    status: completed
  - id: wire-nav-home-settings
    content: 接线：main_window 导航与页面工厂、settings 兜底列表、home 首页卡片同步，用 [subagent:code-explorer] 核查全部引用点
    status: completed
    dependencies:
      - create-buck-thermal-tabs
      - create-bias-crystal-pcb-tabs
      - create-battery-baud-tabs
      - create-reference-lookup-page
  - id: verify-and-docs
    content: 验证：py_compile、lint、offscreen 冒烟；更新 README 与工作记忆
    status: completed
    dependencies:
      - wire-nav-home-settings
---

## 产品概述
为硬件工程师扩充工具集：新增"硬件工具箱"聚合栏目（7 个计算工具，Tab 组织），并将现有"常识查询"栏目升级为速查合集页（6 个速查 Tab）。所有工具沿用功率变换页的交互风格（实时计算、卡片式 UI、macOS 主题），全部离线本地计算。

## 核心功能
**A. 硬件工具箱（新栏目，QTabWidget 内 7 个计算 Tab）**
- DC-DC 开关电源（BUCK）：占空比、电感选型（纹波系数 20%-40% 推荐、标准电感值速查）、输出电容与纹波估算、续流二极管电流/耐压、常用 BUCK 器件库
- 散热与功耗计算：功耗换算、温升与结温、按目标结温反推散热器热阻（RθJA 一体 / RθJC+RθCS+RθSA 分体）、MOSFET/三极管器件库（贴片优先）
- 分压偏置驱动：ADC 分压（含电阻容差误差范围）、LED 限流、三极管开关基极电阻、上拉下拉建议（I2C 4.7k、按钮 10k 等）
- 晶振匹配电容：C1=C2=2(CL-Cs)、频偏估算、常用负载电容速查
- PCB 走线计算：IPC-2221 载流与线宽互算、走线电阻与压降、铜厚（0.5/1/2oz）、mm/mil 换算
- 电池续航估算：mAh/Wh 换算、多模式加权平均电流、续航时间、充电时间（含效率系数）
- 波特率/定时器：MCU 分频重装值定时周期、8051 串口波特率公式、PWM 频率与占空比、常用 MCU 预设（8051/STM32）

**B. 常识查询升级为速查合集页（QTabWidget 内 6 个 Tab）**
- 电阻色环：直接复用现有 ResistorColorCodePage（不重写）
- 单位换算：dBm/mW/V、频率/波长、电容/电阻/频率周期
- E 系列标称值：E6/E12/E24/E48/E96 标准值表（可复制）
- 接口引脚速查：UART/RS232/RS485、I2C、SPI、USB、JTAG/SWD、CAN、RJ45
- 贴片封装尺寸：SOT/SOP/TSSOP/QFN/LQFP/BGA 常见焊盘尺寸
- AWG 线规表：线径/截面积/载流/电阻（30-16AWG）

**C. 导航与配置接线**
- 导航新增"硬件工具箱"（index 5），常识查询顺延 index 6、系统设置 index 7；首页卡片、设置页栏目显隐、导航右键菜单自动适配；首页(0)/系统设置(末位)仍锁定恒可见
- 全部数值 3-4 位有效数字并带单位，输入错误温和提示不弹窗；新增页面走延迟导入，不阻塞启动


## 技术栈
- PyQt6（Python 3.9.0 / PyQt6 6.4.2），沿用现有卡片式 QSS + macOS 主题（app/core/theme.py：ACCENT #007AFF / BG #F2F3F5 / TEXT #1D1D1F）
- 无新增第三方依赖，全部标准库 math + PyQt6

## 实现方案
### 总体策略
- **聚合页模式**：新建 `HardwareToolboxPage`（QTabWidget 承载 7 个独立计算 widget）与 `ReferenceLookupPage`（QTabWidget 承载 6 个速查 Tab），避免导航膨胀；页面工厂延迟导入，保持启动速度。
- **计算风格对齐功率变换页**：QLineEdit textChanged 直连实时刷新、输入框 QDoubleValidator 校验、结果只读行/标签显示、错误时温和提示置灰不弹窗；每 Tab 独立 QWidget 便于后续增删。
- **器件库一致性**：沿用功率变换"类常量 DEFAULT + config 可选覆盖"模式，统一提供 `_load_lib(key, defaults)` 工具方法读取 `hardware_toolbox.<key>_lib` 配置段（缺省回退常量，写盘仅在缺段时一次），DC-DC/散热/波特率三个含器件库的 Tab 共用。

### 关键计算（实现时按此公式）
- BUCK：D=Vout/Vin；L=(Vin-Vout)·D/(fsw·ΔIL)，ΔIL 默认 0.3·Iout；输出纹波 ≈ ΔIL/(8·fsw·Cout)（可加 ESR 项）；二极管反向耐压 ≈ Vin、平均电流 ≈ Iout·(1-D)；标准电感值用 E 系列（1.0/1.5/2.2/3.3/4.7/6.8/10…µH）
- 散热：ΔT=P·Rth；Tj=Ta+ΔT；反推 Rth_max=(Tj_max-Ta)/P - RthJC（分体时）；器件库字段 {rthjc, rthja, pd, 封装}
- PCB 走线：IPC-2221 I=k·ΔT^0.44·A^0.725（外层 k=0.048、内层 0.024，A 单位 mil²）；反向由 I 解 A 再按铜厚转线宽；R=ρ·L/(W·t)，ρ=1.724e-8 Ω·m，1oz≈35µm
- 电池：Wh=mAh·V/1000；续航=Wh/平均功率；充电=容量/充电电流×1.2
- 晶振：C1=C2=2·(CL-Cs)，Cs 默认 3-5pF；频偏按典型拉偏系数估算
- 波特率：8051 Timer1 模式 2：Baud=Fosc/(32·(256-TH1))（SMOD=1 时 16）；PWM：f=Fsys/(分频·(ARR+1))、占空比=CCR/(ARR+1)

### 性能与可靠性
- 计算全部为 O(1) 常量级，无性能瓶颈；textChanged 直连无防抖需求（功率变换页已验证）
- 复用色环电阻页为子 widget（构造无参，已验证可实例化），不重写不侵入
- 新增栏目不破坏现有 hidden_pages 机制：锁定索引用 len(nav_items)-1 自动适配，无需改 `_locked_indexes`

### 执行注意（防回归）
- build_exe*.bat 保持 GBK 编码不动；config.json 不强制新增段（仅缺段时写入 hardware_toolbox）
- 首页 _TOOLS 硬编码必须同步（新增硬件工具箱卡片、常识查询描述与索引更新），否则首页缺卡/跳转错位
- settings_page `_default_nav_items()` 兜底同步 8 项，保证诊断脚本无参实例化兼容
- 延迟导入工厂按 `_page_factory("app.pages.xxx", "XxxPage")` 注册，禁止顶部 import

## 架构设计
```
main_window (SerialDebugTool)
 ├─ nav_items(8项) → 导航按钮 + 右键菜单(QMenu checkable QAction)
 ├─ _page_factories(8项, 延迟导入)
 │    ├─ index5 → HardwareToolboxPage  (QTabWidget: 7个计算Tab, 自含器件库常量)
 │    ├─ index6 → ReferenceLookupPage  (QTabWidget: 6个速查Tab, 复用 ResistorColorCodePage)
 │    └─ index7 → SettingsPage          (栏目显隐卡片, 勾选写 config.hidden_pages)
 ├─ home_page._TOOLS(硬编码)  ← 同步新栏目卡片
 └─ config.json: window.hidden_pages / hardware_toolbox.<key>_lib(可选)
```
组件关系简单清晰，不引入新架构模式；聚合页内部 Tab 复用功率变换页的卡片/表单模式。

## 目录结构
```
app/
├── main_window.py                          [MODIFY] nav_items 插入("🔧","硬件工具箱")(index5)、_page_factories 新增 hardware_toolbox 工厂、常识查询工厂改为 reference_lookup_page；其余(锁定索引/右键菜单)自动适配
├── pages/
│   ├── hardware_toolbox_page.py            [NEW] 类 HardwareToolboxPage：QTabWidget 7 Tab
│   │   ├── DcdcBuckTab      DC-DC BUCK 计算（含器件库与电感标准值速查）
│   │   ├── ThermalTab       散热与功耗（MOSFET/三极管器件库，贴片优先，支持 config 覆盖）
│   │   ├── BiasDriveTab     分压偏置驱动（ADC/LED/三极管/上拉下拉）
│   │   ├── CrystalTab       晶振匹配电容与频偏
│   │   ├── PcbTraceTab      IPC-2221 走线计算与线阻
│   │   ├── BatteryTab       电池续航与充电
│   │   └── BaudTimerTab     波特率/定时器/PWM（8051/STM32 预设）
│   │   共用：_load_lib(key, defaults) 配置覆盖工具、卡片式表单构建辅助
│   ├── reference_lookup_page.py            [NEW] 类 ReferenceLookupPage：QTabWidget 6 Tab
│   │   ├── Tab0 复用 ResistorColorCodePage 实例
│   │   ├── Tab1 单位换算（dBm/mW/V、Hz/波长、µF/nF/pF、kΩ/MΩ、频率周期）
│   │   ├── Tab2 E 系列标称值表（E6/E12/E24/E48/E96 + 复制按钮）
│   │   ├── Tab3 接口引脚速查（UART/RS232/RS485、I2C、SPI、USB、JTAG/SWD、CAN、RJ45）
│   │   ├── Tab4 贴片封装尺寸表（SOT-23/SOT-89/SOT-223/SOP/SSOP/TSSOP/QFN/LQFP/BGA）
│   │   └── Tab5 AWG 线规表（30-16AWG：线径/截面积/载流/Ω·m）
│   │   共用：表格构建 + QApplication.clipboard 复制按钮
│   ├── home_page.py                        [MODIFY] _TOOLS 新增硬件工具箱卡片(index5)、常识查询卡片更新描述与索引(index6)
│   ├── settings_page.py                    [MODIFY] _default_nav_items() 兜底更新为 8 项（含"硬件工具箱"）
│   └── resistor_color_code_page.py         [复用不改] 作为 ReferenceLookupPage 子 Tab
```

## 关键数据契约
- 器件库条目统一字典结构（与功率变换 regulators 同风格）：DC-DC 芯片 {vin_min, vin_max, fsw, 类型}、MOSFET {rthjc, rthja, pd, 封装}、三极管 {hfe, ic_max, pd, 封装}、MCU 预设 {fsys, 分频范围}
- HardwareToolboxPage / ReferenceLookupPage 构造均为 `(parent=None)` 无参，兼容 _page_factory 与潜在脚本实例化
- 所有 Tab 计算结果格式统一为 "值 + 单位"（3-4 位有效数字），无效输入显示 "--"



## 设计风格
延续项目已有的 macOS 风格（Windows 桌面应用）：浅灰背景 #F2F3F5、白色圆角卡片、accent 蓝 #007AFF 强调、细边框 #E5E5EA。两个新页面均为"QTabWidget 聚合页"布局：顶部页标题 + Tab 栏，Tab 栏用 accent 下划线指示当前项。

## 硬件工具箱页
- 顶部：大标题 "硬件工具箱" + 副标题说明，风格同功率变换页
- Tab 栏：DC-DC BUCK / 散热功耗 / 分压偏置 / 晶振匹配 / PCB 走线 / 电池续航 / 波特率定时
- 每个 Tab：左"输入卡片"（QFormLayout 标签+输入框，器件库用 QComboBox 下拉，贴片型号优先）+ 右/下"结果卡片"（灰底 #F5F7FA 只读结果行，关键数值 accent 加粗，越限值（如结温>150°C）红色警示）
- 交互：textChanged 实时刷新，无计算按钮；hover 高亮、焦点蓝环，均走全局主题 QSS

## 常识速查页
- Tab 栏：色环电阻 / 单位换算 / E 系列 / 接口引脚 / 封装尺寸 / AWG 线规
- 速查表：QTableWidget 斑马纹（隔行 #FAFAFC）+ 细边框，列宽自适应；每个表格 Tab 顶部提供"复制全部"按钮（QApplication.clipboard），支持选中行复制
- 色环电阻 Tab 直接嵌入现有 ResistorColorCodePage（保留其内部标题与交互，不重写）
- 单位换算 Tab 用输入框 + 实时互算（如 dBm/mW 双向），与计算类风格统一


## Agent Extensions
### Skill
- **lsp-code-analysis**
  - 用途：实施时定位导航/页面符号（nav_items、_page_factories、ResistorColorCodePage 构造等）的定义与引用，验证新增接线点的语义正确性
  - 预期结果：新增页面与接线无符号遗漏、无引用破坏
### SubAgent
- **code-explorer**
  - 用途：多文件接线完成后，跨文件核查所有引用点（settings_page 栏目卡片、home_page 卡片索引、main_window 工厂注册、脚本调用兼容性）
  - 预期结果：全部调用点适配新栏目，无遗漏、无回归

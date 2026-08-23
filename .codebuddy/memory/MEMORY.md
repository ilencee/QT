# 长期记忆

## 项目: QT (PyQt6 电子工具软件"工作助手")

### 架构与启动
- 主程序 `main.py`；打包名"工作助手"（build_exe.bat one-dir → `dist\工作助手\`，build_exe_onefile.bat 单文件 → `dist\工作助手_单文件\`，均复制 config.json/assets/烧录软件/串口调试助手）。
- 左侧导航页面模块化：每个工具一个 `app/pages/*_page.py`（类 `XxxPage`）；`main_window.py` 用 `_page_factory(module, cls, **kwargs)` 延迟导入页面（重依赖首次打开对应页才加载）；`config.json window.hidden_pages` 控制栏目显隐（首页 0 / 设置末位锁定恒可见，双入口=设置页「📑 栏目显示」卡片 + 导航栏右键菜单）。导航现为 7 栏目：首页/串口调试/文本润色/烧录软件/硬件工具箱/常识查询/系统设置（**功率变换已并入硬件工具箱**，LDO 降压为 Tab，config 段 power_conversion.* 保留）。
- 主题 `app/core/theme.py`：macOS 风（ACCENT #007AFF/BG #F2F3F5/TEXT #1D1D1F/BORDER #E5E5EA）；`system_font()` **只缓存字体族字符串**、每次按参数返回指定字号（勿缓存整个 QFont，会串字号），可选 weight 参数。DPI `setHighDpiScaleFactorRoundingPolicy(PassThrough)` 必须在 QApplication 创建前；Win10 1809 以下温和提示不阻止运行。
- 页面风格：卡片式（`QFrame#card` 圆角）+ 结果格子浅灰底 #F5F7FA；计算类工具实时计算（textChanged 直连，输入错误温和提示不弹窗）。
- **窗口尺寸**（2026-08-23）：恢复 config `window` 段（x/y/width/height）时用 `QGuiApplication.primaryScreen().availableGeometry()` 限制尺寸不超屏、位置收敛到屏幕内（防换屏/高分屏后窗口过高或跑出屏幕无法拖拽）。**内容高的页面必须用 QScrollArea(widgetResizable=True, NoFrame) 包裹**，否则页面 minimumSizeHint 会把窗口最小尺寸撑大、窗口无法缩小（硬件工具箱/常识查询页已加；冒烟验证 minH 从 1000+ 降至 188）。

### 烧录页（programming_software_page.py）
- 详情卡片左图右文（图固定宽 300px，`image` 字段支持字符串/数组，放 `assets/programmers/`，无图灰底占位）。
- 已安装软件三级自动发现：注册表 Uninstall → 开始菜单 .lnk → Program Files；短关键词(<4 字符)词边界匹配；排除安装器 exe；`_launch` 顺序=配置路径→已安装→手动选择；`_find_installed` 缓存只存非空结果，`_launch` 用 force_rescan=True；找不到单次 question 弹窗；启动已装/绿色版零弹窗直接启动 + 按钮"⏳ 正在启动…"2s 反馈。
- 绿色版实为安装包识别：`_is_installer_package(path)` 读前 1MB 搜特征字节（Inno Setup/Nullsoft/InstallShield/Setup Factory/WinRAR SFX/7-Zip SFX/WinZip SFX）+ `_package_cache` 缓存；全安装包时优先启动已安装版本。
- 赛元固件要点：SC-LINK 与 SC-LINK PRO 是两款独立烧录器，固件不通用（SC-LINK 用 V2.x/V3.40，SC-LINK PRO 用 51/ARM 版）；SOC Pro51 配 SC-LINK。
- 烧录器图片已配齐 9 款 11 张（SC-LINK/SC-LINK PRO/XW16Pro/iWriterPro/iWriterGang-4/TWR200/FT200/瑞萨 E1/E2/E2Lite/E20；GD-Link 暂缺图）；`_smoke_all_imgs.py` 自动验证。

### 串口调试页（serial_debug_page.py）
- 不内置收发功能，扫描 `串口调试助手/` 目录并启动现成工具（SSCOM/友善串口调试助手）。
- 安装包徽标：安装包+本机已装 → 绿"✓ 已安装"（tooltip 显示路径）；安装包+未装 → 橙"⚠ 安装包"。友善串口调试助手（Alithon）官方 Windows **仅安装版无绿色版**。`_scan_tools` 给 tool dict 加 `installed` 字段。

### 硬件工具箱（hardware_toolbox_page.py，8 Tab）
BUCK（占空比/电感 E12 就近/纹波/输出电容/续流二极管，芯片库）、**LDO 降压（直接无参复用 `PowerConversionPage`，索引 1）**、散热（RθJA 一体 vs RθJC+RθCS+RθSA 分体反推散热器，MOSFET/三极管库贴片优先）、分压偏置（ADC ±tol 最坏误差/LED 限流/三极管开关饱和系数 k，QStackedWidget 切换）、晶振（C1=C2=2(CL−Cs)+ppm 频偏）、PCB 走线（IPC-2221 双向+线阻压降，1oz=1.378mil）、电池（mAh/Wh+多模式加权+充电效率）、波特率定时（8051 TH1+误差>2% 提示换 11.0592MHz、定时器、PWM）。统一 `_CalcTab` 基类；器件库 config.json `hardware_toolbox.<key>` 覆盖（dcdc_chips/thermal_parts/mcu_presets）缺省回退内置。

### 常识查询（reference_lookup_page.py，6 Tab）
色环电阻（直接无参复用 `ResistorColorCodePage`）/单位换算（dBm/mW/Vrms 50Ω、频率/周期/波长、µF·nF·pF、kΩ·MΩ 双向，textChanged 传 source_key 识别最近修改输入 + blockSignals 防递归；**`rstrip("0")` 仅对含 "." 或 "e" 的值用**，否则 "10"→"1"）/E6~E96 标称值表/接口引脚/贴片封装/AWG 线规（公式生成）。统一 `_LookupTab` 基类（斑马纹只读 QTableWidget + "📋 复制全部"）。

### 功率变换页（power_conversion_page.py）
LDO 降压计算，实时计算，固定型号 Vout 锁定仅"自定义"可编辑，输入错误温和提示不弹窗。

### 文本润色页（text_polish_page.py）
- 所有文档类型"模板即润色内容"：模板编辑区统一标题"📝 模板即润色内容"，`polish()` raw=模板区（图片转 ` [图片] ` 占位，勿用纯空格否则仅图无文误判不脏），system prompt 统一 include_template=False（模板即输入不重复）。
- **无自动保存**：手工「💾 保存模板」按钮写回 config.json（空内容不落盘）；未保存修改切类型/芯片/页面/退出 → 三选确认 `_confirm_unsaved`；`flush_pending_save()` 返回 bool（False=取消），main_window 只处理当前 widget；`_loaded_template_text`=最近保存点供"↺ 恢复原模板"。
- 烧录指导结构：`{constraints:[全局限制], chips:{芯片:{system_role, template}}}`，不分在线/离线双层（旧版由 `_normalize_burn_cfg` 自动迁移）；「⚙️ 模板配置」已改「📌 限制要求」→ `ConstraintsDialog`（角色+限制，保存不关窗）。
- 模板支持插图：`TemplateEdit` 子类粘贴位图/图片文件，base64 data URI 内嵌 HTML 随 template 字段存 config.json。

### 腾讯文档备份（app/core/tencent_docs.py）
- 应用账号 token 免扫码；导入五步（upload-url → PUT COS → async-import → 轮询 import-progress）；**无更新接口，每次备份生成新文档=版本历史**。
- **不支持 .html 扩展名**（fileName 仅 xls/xlsx/csv/doc/docx/txt/text/ppt/pptx/pdf/xmind/pos），备份前用 `build_docx_from_html()`（标准库 zipfile 手写最小 OOXML，支持 data URI 图 + 1px≈9525EMU）转 .docx。
- 凭证两方式：① Access Token 直用（`parse_jwt_payload` 解 clt/sub/exp 自动填，30 天过期重取）；② Client ID/Secret 自动换取（缓存过期重取）。Open ID 三通道优先级：显式传入 > JWT sub > 换取响应。诊断 `scripts/diag_tencent_docs.py`。

### 打包与 Qt 坑
- 打包环境 Python 3.9.0 自带 VCRUNTIME140 旧版 → PyInstaller 打进 exe 报"无法定位序数 380"；**打包前先跑 `scripts\update_vc_runtime.bat`**（System32 14.50 覆盖 Python39 根 + PyQt6\Qt6\bin，需先结束 python 进程）；诊断 `scripts\diag_vc_runtime.py`。
- **build_exe*.bat 编码（2026-08-23 修正）**：必须 **UTF-8(无 BOM)+CRLF** 与脚本第 2 行 `chcp 65001` 匹配，cmd 才能正确解析中文行；GBK 编码 bat + chcp65001 会行断裂（`'open'/'exist' is not recognized`、set 变量失效）。**勿再运行 scripts/fix_bat_encoding.py（转 GBK 会制造此 bug）**。第 1 步图标生成已容错：Pillow 不可用时沿用已有 assets\app.ico（本机 pip 装不上 pillow：清华源 SSL 失败）。icon 用 `%~dp0assets\app.ico` 绝对路径。
- **PyInstaller 收集 app.pages（2026-08-23）**：main_window 用 `importlib.import_module("app.pages.xxx")` 延迟加载页面，**打包命令必须加 `--collect-submodules app.pages`**，否则 exe 运行报 `No module named 'app.pages'`（两个 build bat 均已加）。改 spec 的 hiddenimports 无效，因 bat 每次 `--clean` 重新生成 spec。
- `QLayout.takeAt()` 仅移出布局仍会 paint，必须 `widget.hide(); setParent(None); deleteLater()` 三连。
- PDF 提图（无 PyMuPDF）：正则定位 `<<...>>stream...endstream` 块按 /Filter 解析（DCTDecode 存 JPEG，FlateDecode zlib 解压）。

### 冒烟脚本（scripts/smoke/）
`_smoke_toolbox.py`（8 Tab，含 LDO 降压）/ `_smoke_lookup.py`（6 Tab+单位换算断言）/ `_smoke_pages.py`（导航 7/工厂 7/首页 6 卡/切页后断言全部已实例化，硬件工具箱 index4、常识查询 index5）/ `_smoke_visibility.py`（锁定 0/6、隐藏串口调试+硬件工具箱后首页剩 4 卡、无参构造 7 项）/ `_smoke_review.py`（色环段经 ReferenceLookupPage 取 Tab0，switch_page(5)）/ `_smoke_all_imgs.py`。运行需 `set PYTHONIOENCODING=utf-8`（cmd GBK 无法输出 emoji）+ `QT_QPA_PLATFORM=offscreen`。**坑**：_smoke_visibility 第 1 步隐藏的栏目必须与第 4 步测试的栏目不同，否则设置页初始勾选态断言失败。

## 用户偏好
- 计算类工具要实时（无需点按钮）。
- **不要自己造轮子，直接调用现成工具**（串口用现成 SSCOM/友善串口调试助手，同类需求优先集成）。
- 配置弹窗保存后不关窗口；烧录指导主页面选芯片后直接显示该芯片模板且可编辑。
- 器件选型贴片封装优先（SOT-223/SOT-89/SOT-23）；写入器件库前必须核实真实封装规格（78L05/78L08=SOT-89、AMS1117/LM1117=SOT-223、78L05 直插=TO-92）。

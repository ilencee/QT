# 工作助手 (串口调试工具)

基于 PyQt6 的电子工程桌面工具，集成了串口调试、功率变换计算、电阻色环查询等功能。

## 📁 项目架构

```
tool/
├── main.py                    # 统一入口 (python main.py)
├── requirements.txt           # 依赖清单
├── config.json                # 应用配置 (默认参数 / API / 型号库)
├── assets/
│   └── icon.png               # 应用图标
├── app/                       # 应用主包
│   ├── main_window.py         # 主窗口 (导航栏 + 页面切换 + 懒加载)
│   ├── pages/                 # 功能页面
│   │   ├── home_page.py              # 首页概览 (状态卡片)
│   │   ├── serial_debug_page.py      # 串口调试页面
│   │   ├── power_conversion_page.py  # 功率变换计算 (LDO/电阻选型/AI 分析)
│   │   ├── text_polish_page.py       # 文本润色 (工艺要求/测试流程/烧录指导, 芯片×烧录方式模板)
│   │   ├── programming_software_page.py # 烧录软件速查 (各芯片官方烧录工具)
│   │   ├── resistor_color_code_page.py # 电阻色环查询
│   │   └── placeholder_page.py       # 占位页面 (未开发功能)
│   ├── core/                  # 核心模块
│   │   ├── config_manager.py  # 配置管理 (config.json)
│   │   ├── deepseek_client.py # DeepSeek API 客户端 (线程/结果弹窗, 多页面共享)
│   │   └── style_manager.py   # 统一样式管理
│   └── tools/                 # 独立工具 (可单独运行)
│       ├── serial_port.py     # SerialStudio 独立串口调试器
│       └── learn.py           # 无边框窗口示例
├── scripts/
│   └── test_resistor_plan.py  # 电阻选型算法测试脚本
└── archive/                   # 历史备份 (旧版代码)
    └── Untitled-1.py
```

## 🚀 运行

```bash
pip install -r requirements.txt
python main.py
```

独立工具:

```bash
python app/tools/serial_port.py   # SerialStudio
```

## 🔧 配置说明 (config.json)

- `power_conversion.defaults`: 功率变换页默认参数（型号、电压、电流等）
- `power_conversion.regulators`: LDO 稳压器型号库
- `power_conversion.api`: DeepSeek API Key（用于 AI 分析）
- `text_polish.types`: 文本润色各文档类型的模板与限制（工艺要求/测试流程/烧录指导）
  - 工艺要求 / 测试流程: 每项含 `system_role`（角色设定）、`template`（文档模板）、`constraints`（限制条件数组）
  - 烧录指导: `modes`（烧录方式列表）+ `chips`（按芯片厂商，如中微爱芯/十速/兆易创新/赛元），每个芯片内按在线/离线烧录分别配置模板；新增芯片即在 `chips` 下加一项（也可在页面「⚙️ 模板配置」中直接新增）
  - 修改保存后立即生效，无需重启
- `programming_software.chips`: 烧录软件速查页数据（各芯片的烧录器列表）
  - 一个芯片可配置多个烧录器：`programmers` 数组，一项一个烧录器（如兆易创新含 XW16Pro Standalone Programmer / FT200 / GD32 All-In-One Programmer），每项含 `name`（烧录器名）、`exe`、`desc`、`hardware`、`usage`、`note`；页面用下拉框选择烧录器，详情与启动均针对当前烧录器
  - `exe`: 该烧录器软件的可执行文件，支持完整路径或程序名（自动在 PATH 中查找），多个候选用 `;` 分隔；为空时可在页面「🚀 启动烧录软件」弹窗中现场选择并自动保存到当前烧录器
  - 软件位于项目目录内时自动存为**相对路径**（如 `XW16Pro_StandaloneProgrammer/.../xxx.exe`），整个项目文件夹移动/改名后依然有效；目录外的软件保存绝对路径
  - 旧版平铺结构（每芯片单个 `software`/`exe` 字段）在页面启动时会自动迁移为 `programmers` 列表

## 🎯 架构设计

- **模块化**：页面按功能拆分到 `app/pages/`，核心逻辑在 `app/core/`
- **懒加载**：主窗口启动只创建首页，其余页面首次点击时创建，加快启动速度
- **独立工具隔离**：`app/tools/` 下的工具各自独立运行，不依赖主窗口
- **配置持久化**：默认参数、型号库、API 统一由 `config.json` 管理，支持手动编辑

## 📝 添加新页面

1. 在 `app/pages/` 下创建页面文件（如 `new_feature_page.py`）
2. 在 `app/main_window.py` 的 `_page_factories` 中添加工厂函数
3. 在 `nav_items` 中添加对应导航项

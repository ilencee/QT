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
│   │   ├── text_polish_page.py       # 文本润色 (工艺要求/测试流程/烧录指导)
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
- `text_polish.types`: 文本润色各文档类型的模板与限制（工艺要求/测试流程/烧录指导），每项含 `system_role`（角色设定）、`template`（文档模板）、`constraints`（限制条件数组），修改后重启生效

## 🎯 架构设计

- **模块化**：页面按功能拆分到 `app/pages/`，核心逻辑在 `app/core/`
- **懒加载**：主窗口启动只创建首页，其余页面首次点击时创建，加快启动速度
- **独立工具隔离**：`app/tools/` 下的工具各自独立运行，不依赖主窗口
- **配置持久化**：默认参数、型号库、API 统一由 `config.json` 管理，支持手动编辑

## 📝 添加新页面

1. 在 `app/pages/` 下创建页面文件（如 `new_feature_page.py`）
2. 在 `app/main_window.py` 的 `_page_factories` 中添加工厂函数
3. 在 `nav_items` 中添加对应导航项

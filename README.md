# 串口调试工具 - 项目结构说明

## 📁 项目架构

本项目采用**模块化设计**，将不同界面分离到独立文件中，便于维护和扩展。

### 核心文件说明

#### 1. **test1.py** - 主程序入口
- **职责**：窗口框架、导航栏、页面切换逻辑
- **包含内容**：
  - `SerialDebugTool` 类：主窗口类
  - 导航按钮管理
  - 页面切换逻辑
  - 导航栏展开/收起功能
  - 全局样式应用

#### 2. **home_page.py** - 首页模块
- **类名**：`HomePage`
- **功能**：显示串口状态、数据统计卡片
- **特点**：可滚动区域，网格布局展示信息卡片

#### 3. **serial_debug_page.py** - 串口调试页面
- **类名**：`SerialDebugPage`
- **功能**：串口配置、数据收发显示
- **特点**：包含串口选择、波特率设置、数据显示区域

#### 4. **placeholder_page.py** - 占位页面模块
- **类名**：`PlaceholderPage`
- **功能**：用于尚未开发的功能页面
- **参数**：接收标题和图标，显示"此功能正在开发中..."
- **使用场景**：BOM整理、文档图纸、走线计算、功率变换、系统设置

#### 5. **resistor_color_code_page.py** - 电阻色环查询页面
- **类名**：`ResistorColorCodePage`
- **功能**：电阻色环对照表、快速查询计算器
- **特点**：
  - 完整的色环颜色对照表
  - 下拉框选择器
  - 自动计算电阻值
  - 支持多种单位显示（Ω, kΩ, MΩ, GΩ）

## 🎯 架构优势

### 1. **易于维护**
- 每个页面独立管理，修改一个页面不影响其他页面
- 代码职责清晰，便于定位问题

### 2. **便于扩展**
- 新增页面只需创建新文件，在主程序中注册即可
- 不需要修改现有页面代码

### 3. **团队协作友好**
- 不同开发者可以同时开发不同页面
- 减少代码冲突

### 4. **代码复用**
- 通用组件可以提取为独立模块
- 占位页面可重复使用

## 📝 如何添加新页面

### 步骤 1：创建页面文件
```python
# new_feature_page.py
from PyQt6.QtWidgets import QWidget, QVBoxLayout, QLabel
from PyQt6.QtGui import QFont

class NewFeaturePage(QWidget):
    def __init__(self):
        super().__init__()
        self.initUI()
    
    def initUI(self):
        layout = QVBoxLayout(self)
        # 添加你的界面元素
        label = QLabel("新功能页面")
        layout.addWidget(label)
```

### 步骤 2：在主程序中导入
```python
# test1.py
from new_feature_page import NewFeaturePage
```

### 步骤 3：在 initUI 中实例化
```python
self.page_new_feature = NewFeaturePage()
self.stacked_widget.addWidget(self.page_new_feature)
```

### 步骤 4：添加到导航项
```python
self.nav_items = [
    ("🏠", "首页概览"),
    ("🔌", "串口调试"),
    # ... 其他项
    ("✨", "新功能")  # 添加新项
]
```

## 🔧 运行项目

```bash
python test1.py
```

## 📌 注意事项

1. **依赖管理**：确保已安装 PyQt6
   ```bash
   pip install PyQt6
   ```

2. **导入顺序**：主程序必须先导入所有页面模块

3. **命名规范**：
   - 文件名：小写+下划线（如 `home_page.py`）
   - 类名：大驼峰（如 `HomePage`）

4. **页面通信**：如需页面间通信，可通过主程序传递信号或共享数据

## 🚀 后续优化建议

1. **样式管理**：✅ 已完成 - 使用 `style_manager.py` 统一管理所有UI组件样式
2. **配置管理**：✅ 已完成 - 使用 `config_manager.py` 管理串口配置等设置
3. **日志系统**：添加日志记录功能
4. **单元测试**：为各个页面编写测试用例

## 📝 使用说明

### 样式管理器 (style_manager.py)

```python
from style_manager import StyleManager

# 应用卡片样式
card = QFrame()
StyleManager.card_info(card, color="#409EFF")

# 应用滚动区域样式
scroll = QScrollArea()
StyleManager.scroll_area_clean(scroll)

# 应用按钮样式
button = QPushButton("按钮")
StyleManager.button_modern_flat(button)
```

### 配置管理器 (config_manager.py)

```python
from config_manager import ConfigManager

# 创建配置管理器实例
config = ConfigManager("config.json")

# 获取串口配置
serial_config = config.get_serial_config()
params = config.get_full_serial_params()

# 设置串口参数
config.set_serial_port("COM3")
config.set_baudrate(115200)

# 保存配置到文件
config.save_config()

# 通过路径访问配置
baudrate = config.get_value("serial_port.baudrate", default=9600)
config.set_value("window.theme", "macOS Light")
```


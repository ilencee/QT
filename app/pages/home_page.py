"""首页概览: 工具快捷入口卡片 (点击跳转对应页面)"""

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QGridLayout, QLabel, QPushButton,
)
from PyQt6.QtCore import Qt

from app.core.theme import system_font, TEXT, TEXT_SECONDARY, TEXT_LIGHT, ACCENT


# 工具卡片数据: (图标, 名称, 描述, 导航索引, 主题色)
_TOOLS = [
    ("🔌", "串口调试", "串口数据收发 / HEX 显示 / 定时发送", 1, "#409EFF"),
    ("📄", "文本润色", "AI 按模板润色文档与烧录指导", 2, "#67C23A"),
    ("💾", "烧录软件", "芯片厂商 / 烧录器管理与官网入口", 3, "#E6A23C"),
    ("🔧", "硬件工具箱", "LDO / BUCK 电源 / 散热 / PCB / 电池等 8 大计算", 4, "#007AFF"),
    ("📚", "常识查询", "色环电阻 / 单位换算 / E 系列 / 接口 / 封装 / AWG", 5, "#909399"),
    ("⚙️", "系统设置", "软件配置与偏好设置", 6, "#333333"),
]


def _card_style(color: str) -> str:
    """工具卡片样式: 大圆角白色卡片 + 左侧主题色条 + hover 反馈 (QSS 模拟, 无真实投影开销)"""
    return (
        f"QPushButton {{ background: white; border: 1px solid #E5E5EA;"
        f"border-left: 4px solid {color}; border-radius: 14px;"
        f"text-align: left; padding: 18px 22px; }}"
        f"QPushButton:hover {{ border-color: {ACCENT}; background: #F7F9FC; }}"
        "QPushButton:pressed { background: #ECF5FF; }"
    )


class HomePage(QWidget):
    """首页: 工具导航卡片, 点击回调 on_navigate(页面索引); 支持按 hidden_pages 同步隐藏"""

    def __init__(self, on_navigate=None, hidden_pages=()):
        super().__init__()
        self.on_navigate = on_navigate
        self._hidden_pages = set(hidden_pages or ())
        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(20)

        # 欢迎语
        welcome = QLabel("👋 欢迎使用 工作助手")
        _welcome_font = system_font(22)
        _welcome_font.setBold(True)
        welcome.setFont(_welcome_font)
        welcome.setStyleSheet(f"color: {TEXT};")
        layout.addWidget(welcome)

        subtitle = QLabel("集成串口调试、AI 文本润色、烧录软件管理、硬件计算与电子常识查询的桌面工具")
        subtitle.setFont(system_font(12))
        subtitle.setStyleSheet(f"color: {TEXT_SECONDARY};")
        layout.addWidget(subtitle)

        layout.addSpacing(8)

        # 工具卡片网格 (实例属性, 供 set_hidden_pages 重建)
        self.grid = QGridLayout()
        self.grid.setSpacing(16)
        self._rebuild_cards()
        layout.addLayout(self.grid)

        layout.addStretch()

        # 底部说明
        footer = QLabel("💡 点击卡片快速进入对应工具")
        footer.setFont(system_font(10))
        footer.setStyleSheet(f"color: {TEXT_LIGHT};")
        layout.addWidget(footer)

    # ==================== 栏目显隐同步 ====================
    def set_hidden_pages(self, hidden):
        """根据隐藏栏目集合重建卡片网格 (与导航栏显隐同步)"""
        self._hidden_pages = set(hidden or ())
        self._rebuild_cards()

    def _rebuild_cards(self):
        """按 _TOOLS 过滤重建工具卡片"""
        # 移除旧卡片 (Qt 坑: takeAt 仅移除布局关系, 必须 hide + setParent(None) + deleteLater 三连)
        while self.grid.count():
            item = self.grid.takeAt(0)
            w = item.widget()
            if w is not None:
                w.hide()
                w.setParent(None)
                w.deleteLater()

        visible = [t for t in _TOOLS if t[1] not in self._hidden_pages]
        for i, (icon, name, desc, index, color) in enumerate(visible):
            card = self._create_card(icon, name, desc, index, color)
            row, col = divmod(i, 2)
            self.grid.addWidget(card, row, col)

    def _create_card(self, icon, name, desc, index, color):
        """创建工具导航卡片"""
        text = f"{icon}  {name}\n{desc}"
        card = QPushButton(text)
        card.setMinimumHeight(96)
        card.setCursor(Qt.CursorShape.PointingHandCursor)
        card.setFont(system_font(13))
        card.setStyleSheet(_card_style(color))
        if self.on_navigate is not None:
            card.clicked.connect(lambda _=False, idx=index: self.on_navigate(idx))
        return card

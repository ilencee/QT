"""macOS 风格主题：调色板 + 全局 QSS + 字体策略。

零新依赖（纯 QSS + Qt 内置能力）。main() 启动时调用 apply_theme(app) 一次，
各页面局部样式优先级高于全局 QSS，无需逐一改造。
"""

from PyQt6.QtGui import QFont, QFontDatabase

# ==================== macOS 调色板 ====================
ACCENT = "#007AFF"            # 主色（macOS 蓝）
ACCENT_HOVER = "#0A84FF"
ACCENT_PRESSED = "#0060DF"
BG = "#F2F3F5"                # 窗口背景（浅灰磨砂感）
CARD = "#FFFFFF"              # 卡片背景
TEXT = "#1D1D1F"              # 主文字（近黑）
TEXT_SECONDARY = "#6E6E73"    # 次级文字
TEXT_LIGHT = "#C7C7CC"        # 弱化文字
BORDER = "#E5E5EA"            # 分隔线 / 边框
SUCCESS = "#34C759"
DANGER = "#FF3B30"
WARNING = "#FF9500"

# 中文字体族（按优先级，英文版 Windows 自动回退）
_CJK_FAMILIES = ("Microsoft YaHei UI", "Microsoft YaHei", "PingFang SC", "Segoe UI")

_font_cache = None


def system_font(point_size: int = 10, weight=None) -> QFont:
    """返回当前系统最合适的 UI 字体（字体族启动时检测一次并缓存）。

    - 中文系统：Microsoft YaHei UI / Microsoft YaHei
    - 英文系统：Segoe UI（中文字形由 Qt 自动 fallback）
    - weight: 可选 QFont.Weight, 如 QFont.Weight.Bold
    """
    global _font_cache
    if _font_cache is None:
        family = ""
        try:
            families = set(QFontDatabase.families())
            family = next((f for f in _CJK_FAMILIES if f in families), "")
        except Exception:
            family = ""
        _font_cache = family
    font = QFont(_font_cache, point_size)
    if weight is not None:
        font.setWeight(weight)
    return font


def apply_theme(app):
    """应用 macOS 风格主题：全局字体 + 全局 QSS（QApplication 创建后调用一次）"""
    app.setFont(system_font(10))
    app.setStyleSheet(GLOBAL_QSS)


GLOBAL_QSS = f"""
/* ===== 基础 ===== */
QWidget {{
    color: {TEXT};
}}
QMainWindow, QDialog {{
    background: {BG};
}}
QToolTip {{
    background: rgba(255, 255, 255, 0.95);
    color: {TEXT};
    border: 1px solid {BORDER};
    border-radius: 6px;
    padding: 5px 9px;
}}
QMessageBox {{
    background: {BG};
}}

/* ===== 菜单（macOS 风格圆角菜单） ===== */
QMenu {{
    background: rgba(246, 246, 246, 0.98);
    border: 1px solid rgba(0, 0, 0, 0.12);
    border-radius: 10px;
    padding: 6px;
}}
QMenu::item {{
    padding: 7px 22px;
    border-radius: 6px;
    color: {TEXT};
    background: transparent;
}}
QMenu::item:selected {{
    background: rgba(0, 122, 255, 0.14);
    color: {ACCENT};
}}
QMenu::item:disabled {{
    color: {TEXT_LIGHT};
}}
QMenu::separator {{
    height: 1px;
    background: {BORDER};
    margin: 6px 10px;
}}

/* ===== 细条滚动条（8px 圆角，hover 增深） ===== */
QScrollBar:vertical {{
    background: transparent;
    width: 8px;
    margin: 2px;
}}
QScrollBar::handle:vertical {{
    background: rgba(0, 0, 0, 0.16);
    border-radius: 4px;
    min-height: 30px;
}}
QScrollBar::handle:vertical:hover {{
    background: rgba(0, 0, 0, 0.32);
}}
QScrollBar:horizontal {{
    background: transparent;
    height: 8px;
    margin: 2px;
}}
QScrollBar::handle:horizontal {{
    background: rgba(0, 0, 0, 0.16);
    border-radius: 4px;
    min-width: 30px;
}}
QScrollBar::handle:horizontal:hover {{
    background: rgba(0, 0, 0, 0.32);
}}
QScrollBar::add-line, QScrollBar::sub-line {{
    width: 0;
    height: 0;
}}
QScrollBar::add-page, QScrollBar::sub-page {{
    background: transparent;
}}

/* ===== 分割条 ===== */
QSplitter::handle {{
    background: transparent;
    width: 1px;
}}

/* ===== 复选框 / 单选（accent 勾选色） ===== */
QCheckBox, QRadioButton {{
    spacing: 8px;
    color: {TEXT};
}}
QCheckBox::indicator, QRadioButton::indicator {{
    width: 16px;
    height: 16px;
}}
QCheckBox::indicator {{
    border: 2px solid #C7C7CC;
    border-radius: 5px;
    background: white;
}}
QCheckBox::indicator:hover {{
    border-color: {ACCENT};
}}
QCheckBox::indicator:checked {{
    background: {ACCENT};
    border-color: {ACCENT};
}}
QCheckBox::indicator:disabled {{
    background: #F2F3F5;
    border-color: #D8D8DC;
}}
QRadioButton::indicator {{
    border: 2px solid #C7C7CC;
    border-radius: 8px;
    background: white;
}}
QRadioButton::indicator:checked {{
    border: 5px solid {ACCENT};
    background: white;
}}

/* ===== 输入控件（聚焦蓝环） ===== */
QLineEdit, QTextEdit, QPlainTextEdit, QSpinBox, QDoubleSpinBox, QComboBox {{
    background: white;
    border: 1px solid #D1D1D6;
    border-radius: 8px;
    padding: 6px 10px;
    selection-background-color: rgba(0, 122, 255, 0.25);
}}
QLineEdit:hover, QTextEdit:hover, QPlainTextEdit:hover,
QSpinBox:hover, QDoubleSpinBox:hover, QComboBox:hover {{
    border-color: #B8B8BD;
}}
QLineEdit:focus, QTextEdit:focus, QPlainTextEdit:focus,
QSpinBox:focus, QDoubleSpinBox:focus, QComboBox:focus {{
    border: 1px solid {ACCENT};
}}
QComboBox::drop-down {{
    border: none;
    width: 24px;
}}
QComboBox QAbstractItemView {{
    background: white;
    border: 1px solid {BORDER};
    border-radius: 8px;
    padding: 4px;
    selection-background-color: rgba(0, 122, 255, 0.12);
    selection-color: {ACCENT};
}}

/* ===== 按钮兜底（局部样式优先，此处仅给未定制按钮基础外观） ===== */
QPushButton {{
    background: rgba(0, 0, 0, 0.05);
    color: {TEXT};
    border: none;
    border-radius: 8px;
    padding: 6px 16px;
}}
QPushButton:hover {{
    background: rgba(0, 0, 0, 0.09);
}}
QPushButton:pressed {{
    background: rgba(0, 0, 0, 0.13);
}}
QPushButton:disabled {{
    color: {TEXT_LIGHT};
    background: rgba(0, 0, 0, 0.03);
}}
"""

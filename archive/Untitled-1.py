'''
Author: ilencee 862491025@qq.com
Date: 2026-04-13 21:54:41
LastEditors: ilencee 862491025@qq.com
LastEditTime: 2026-04-13 23:11:40
FilePath: /QT/Untitled-1.py
Description: 

Copyright (c) 2026 by ${git_name_email}, All Rights Reserved. 
'''
import sys
import os
import json
import serial  
import serial.tools.list_ports  
from datetime import datetime
from dataclasses import dataclass, asdict
from typing import Optional, List, Callable
from enum import Enum, auto
from collections import deque

# type: ignore[attr-defined]  # 忽略 pyserial 类型检查问题

from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QPushButton, QComboBox, QTextEdit, QLineEdit, QCheckBox,
    QSpinBox, QFrame, QSplitter, QGroupBox, QGridLayout, QStatusBar,
    QFileDialog, QMessageBox, QMenu, QSystemTrayIcon, QStyleFactory,
    QSizePolicy, QGraphicsDropShadowEffect, QScrollArea, QToolButton,
    QMenuBar, QToolBar, QDialog, QProgressBar
)
from PyQt6.QtCore import (
    Qt, QThread, pyqtSignal, QTimer, QSize, QPropertyAnimation, QEasingCurve,
    QPoint, QRect, QSettings, QStandardPaths
)
from PyQt6.QtGui import (
    QColor, QPalette, QFont, QIcon, QAction, QPainter, QLinearGradient,
    QBrush, QPen, QFontDatabase, QCursor, QKeySequence, QShortcut
)


# ==================== 主题配置 ====================
class ThemeManager:
    """主题管理器 - 支持多个主题切换"""
    
    # 当前使用的主题名称
    current_theme = "macOS Light"
    
    # 所有主题配置
    THEMES = {
        "macOS Light": {
            "name": "macOS 浅色",
            "PRIMARY": "#007AFF",
            "PRIMARY_LIGHT": "#4DA3FF",
            "PRIMARY_DARK": "#0051D5",
            "BG_DARKEST": "#F5F5F7",
            "BG_DARK": "#FFFFFF",
            "BG_CARD": "#FFFFFF",
            "BG_INPUT": "#F5F5F7",
            "BG_HOVER": "#E8E8ED",
            "TEXT_PRIMARY": "#1D1D1F",
            "TEXT_SECONDARY": "#6E6E73",
            "TEXT_MUTED": "#86868B",
            "SUCCESS": "#34C759",
            "WARNING": "#FF9500",
            "ERROR": "#FF3B30",
            "INFO": "#007AFF",
            "BORDER": "#D1D1D6",
            "BORDER_LIGHT": "#E5E5EA",
            "FONT_FAMILY": ".AppleSystemUIFont",
            "FONT_SIZE": 13,
            "STYLE_NAME": "macintosh",
        },
        
        "Dark Mode": {
            "name": "深色模式",
            "PRIMARY": "#6366F1",
            "PRIMARY_LIGHT": "#818CF8",
            "PRIMARY_DARK": "#4F46E5",
            "BG_DARKEST": "#0F0F11",
            "BG_DARK": "#1A1A1F",
            "BG_CARD": "#232329",
            "BG_INPUT": "#2A2A32",
            "BG_HOVER": "#2F2F38",
            "TEXT_PRIMARY": "#F8FAFC",
            "TEXT_SECONDARY": "#94A3B8",
            "TEXT_MUTED": "#64748B",
            "SUCCESS": "#10B981",
            "WARNING": "#F59E0B",
            "ERROR": "#EF4444",
            "INFO": "#3B82F6",
            "BORDER": "#334155",
            "BORDER_LIGHT": "#475569",
            "FONT_FAMILY": "Segoe UI",
            "FONT_SIZE": 12,
            "STYLE_NAME": "Fusion",
        },
        
        "GitHub Light": {
            "name": "GitHub 浅色",
            "PRIMARY": "#0969DA",
            "PRIMARY_LIGHT": "#218BFF",
            "PRIMARY_DARK": "#0550AE",
            "BG_DARKEST": "#F6F8FA",
            "BG_DARK": "#FFFFFF",
            "BG_CARD": "#FFFFFF",
            "BG_INPUT": "#F6F8FA",
            "BG_HOVER": "#EBF0F4",
            "TEXT_PRIMARY": "#24292F",
            "TEXT_SECONDARY": "#57606A",
            "TEXT_MUTED": "#6E7781",
            "SUCCESS": "#1A7F37",
            "WARNING": "#BF8700",
            "ERROR": "#CF222E",
            "INFO": "#0969DA",
            "BORDER": "#D0D7DE",
            "BORDER_LIGHT": "#E8ECF0",
            "FONT_FAMILY": "Segoe UI",
            "FONT_SIZE": 13,
            "STYLE_NAME": "Fusion",
        },
        
        "Nord": {
            "name": "Nord 北欧",
            "PRIMARY": "#88C0D0",
            "PRIMARY_LIGHT": "#8FBCBB",
            "PRIMARY_DARK": "#5E81AC",
            "BG_DARKEST": "#2E3440",
            "BG_DARK": "#3B4252",
            "BG_CARD": "#434C5E",
            "BG_INPUT": "#4C566A",
            "BG_HOVER": "#D8DEE9",
            "TEXT_PRIMARY": "#ECEFF4",
            "TEXT_SECONDARY": "#D8DEE9",
            "TEXT_MUTED": "#E5E9F0",
            "SUCCESS": "#A3BE8C",
            "WARNING": "#EBCB8B",
            "ERROR": "#BF616A",
            "INFO": "#81A1C1",
            "BORDER": "#4C566A",
            "BORDER_LIGHT": "#5E6A7D",
            "FONT_FAMILY": "Consolas",
            "FONT_SIZE": 13,
            "STYLE_NAME": "Fusion",
        },
    }
    
    @classmethod
    def get_theme(cls, theme_name=None):
        """获取主题配置"""
        name = theme_name or cls.current_theme
        if name not in cls.THEMES:
            name = "macOS Light"
        return cls.THEMES[name]
    
    @classmethod
    def switch_theme(cls, theme_name):
        """切换主题"""
        if theme_name in cls.THEMES:
            cls.current_theme = theme_name
            return True
        return False
    
    @classmethod
    def get_theme_list(cls):
        """获取所有主题名称列表"""
        return list(cls.THEMES.keys())
    
    @classmethod
    def apply(cls, app: QApplication):
        """应用当前主题"""
        theme = cls.get_theme()
        
        # 设置样式
        try:
            app.setStyle(QStyleFactory.create(theme["STYLE_NAME"]))  # type: ignore
        except:
            app.setStyle(QStyleFactory.create("Fusion"))
        
        palette = QPalette()
        palette.setColor(QPalette.ColorRole.Window, QColor(theme["BG_DARK"]))
        palette.setColor(QPalette.ColorRole.WindowText, QColor(theme["TEXT_PRIMARY"]))
        palette.setColor(QPalette.ColorRole.Base, QColor(theme["BG_CARD"]))
        palette.setColor(QPalette.ColorRole.AlternateBase, QColor(theme["BG_INPUT"]))
        palette.setColor(QPalette.ColorRole.ToolTipBase, QColor(theme["BG_CARD"]))
        palette.setColor(QPalette.ColorRole.ToolTipText, QColor(theme["TEXT_PRIMARY"]))
        palette.setColor(QPalette.ColorRole.Text, QColor(theme["TEXT_PRIMARY"]))
        palette.setColor(QPalette.ColorRole.Button, QColor(theme["BG_CARD"]))
        palette.setColor(QPalette.ColorRole.ButtonText, QColor(theme["TEXT_PRIMARY"]))
        palette.setColor(QPalette.ColorRole.Highlight, QColor(theme["PRIMARY"]))
        palette.setColor(QPalette.ColorRole.HighlightedText, QColor("#FFFFFF"))
        
        app.setPalette(palette)
        
        # 设置字体
        font_family = theme["FONT_FAMILY"]
        font_size = theme["FONT_SIZE"]
        font = QFont(font_family, font_size)
        if font_family not in QFontDatabase.families():
            font = QFont("Segoe UI", font_size)
        app.setFont(font)


# 为了兼容旧代码，创建一个别名
Theme = ThemeManager


# ==================== 样式表生成器 ====================
def generate_stylesheet(theme_name=None):
    """根据主题生成样式表"""
    theme = ThemeManager.get_theme(theme_name)
    
    return f"""
QMainWindow {{
    background-color: {theme['BG_DARK']};
}}

/* 卡片容器 - 圆角和阴影 */
QFrame#card {{
    background-color: {theme['BG_CARD']};
    border-radius: 16px;
    border: 0.5px solid {theme['BORDER_LIGHT']};
}}

/* 按钮样式 */
QPushButton {{
    background-color: {theme['BG_INPUT']};
    color: {theme['TEXT_PRIMARY']};
    border: none;
    border-radius: 8px;
    padding: 10px 20px;
    font-size: {theme['FONT_SIZE']}px;
    font-weight: 500;
    min-height: 36px;
}}

QPushButton:hover {{
    background-color: {theme['BG_HOVER']};
}}

QPushButton:pressed {{
    background-color: {theme['BORDER']};
}}

QPushButton#primary {{
    background-color: {theme['PRIMARY']};
    color: white;
}}

QPushButton#primary:hover {{
    background-color: {theme['PRIMARY_LIGHT']};
}}

QPushButton#primary:pressed {{
    background-color: {theme['PRIMARY_DARK']};
}}

QPushButton#danger {{
    background-color: {theme['ERROR']};
    color: white;
}}

QPushButton#success {{
    background-color: {theme['SUCCESS']};
    color: white;
}}

/* 输入框样式 */
QLineEdit, QTextEdit, QComboBox {{
    background-color: {theme['BG_INPUT']};
    color: {theme['TEXT_PRIMARY']};
    border: 1px solid transparent;
    border-radius: 8px;
    padding: 10px 14px;
    font-size: {theme['FONT_SIZE']}px;
    selection-background-color: {theme['PRIMARY']};
}}

QLineEdit:focus, QTextEdit:focus, QComboBox:focus {{
    border: 2px solid {theme['PRIMARY']};
    background-color: {theme['BG_CARD']};
}}

QComboBox::drop-down {{
    border: none;
    width: 28px;
}}

QComboBox::down-arrow {{
    image: none;
    border-left: 5px solid transparent;
    border-right: 5px solid transparent;
    border-top: 7px solid {theme['TEXT_SECONDARY']};
    margin-right: 8px;
}}

QComboBox QAbstractItemView {{
    background-color: {theme['BG_CARD']};
    border: 1px solid {theme['BORDER']};
    selection-background-color: {theme['PRIMARY']};
    selection-color: white;
    border-radius: 8px;
    outline: none;
    padding: 4px;
}}

/* 复选框样式 */
QCheckBox {{
    color: {theme['TEXT_PRIMARY']};
    spacing: 10px;
    font-size: {theme['FONT_SIZE']}px;
}}

QCheckBox::indicator {{
    width: 20px;
    height: 20px;
    border-radius: 6px;
    border: 2px solid {theme['BORDER']};
    background-color: {theme['BG_CARD']};
}}

QCheckBox::indicator:checked {{
    background-color: {theme['PRIMARY']};
    border-color: {theme['PRIMARY']};
}}

QCheckBox::indicator:hover {{
    border-color: {theme['PRIMARY']};
}}

/* 分组框样式 */
QGroupBox {{
    background-color: {theme['BG_CARD']};
    border: 0.5px solid {theme['BORDER_LIGHT']};
    border-radius: 16px;
    margin-top: 16px;
    padding-top: 20px;
    font-weight: 600;
    font-size: {theme['FONT_SIZE']}px;
    color: {theme['TEXT_PRIMARY']};
}}

QGroupBox::title {{
    subcontrol-origin: margin;
    left: 18px;
    padding: 0 10px;
    color: {theme['TEXT_PRIMARY']};
    font-size: {theme['FONT_SIZE']}px;
}}

/* 滚动条样式 */
QScrollBar:vertical {{
    background-color: transparent;
    width: 10px;
    margin: 0px;
}}

QScrollBar::handle:vertical {{
    background-color: rgba(0, 0, 0, 0.2);
    border-radius: 5px;
    min-height: 40px;
    margin: 2px;
}}

QScrollBar::handle:vertical:hover {{
    background-color: rgba(0, 0, 0, 0.35);
}}

QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
    height: 0px;
}}

QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {{
    background: none;
}}

QScrollBar:horizontal {{
    background-color: transparent;
    height: 10px;
    margin: 0px;
}}

QScrollBar::handle:horizontal {{
    background-color: rgba(0, 0, 0, 0.2);
    border-radius: 5px;
    min-width: 40px;
    margin: 2px;
}}

QScrollBar::handle:horizontal:hover {{
    background-color: rgba(0, 0, 0, 0.35);
}}

/* 状态栏样式 */
QStatusBar {{
    background-color: {theme['BG_DARKEST']};
    color: {theme['TEXT_SECONDARY']};
    border-top: 0.5px solid {theme['BORDER_LIGHT']};
    font-size: 12px;
    padding: 4px 8px;
}}

/* 标签样式 */
QLabel#title {{
    font-size: {theme['FONT_SIZE'] + 4}px;
    font-weight: 600;
    color: {theme['TEXT_PRIMARY']};
    letter-spacing: -0.5px;
}}

QLabel#subtitle {{
    font-size: 12px;
    color: {theme['TEXT_SECONDARY']};
    font-weight: 400;
}}

QLabel#status_connected {{
    color: {theme['SUCCESS']};
    font-weight: 500;
}}

QLabel#status_disconnected {{
    color: {theme['TEXT_MUTED']};
    font-weight: 500;
}}

/* 工具按钮样式 */
QToolButton {{
    background-color: transparent;
    border: none;
    border-radius: 6px;
    padding: 8px;
    font-size: 16px;
}}

QToolButton:hover {{
    background-color: {theme['BG_HOVER']};
}}

QToolButton:pressed {{
    background-color: {theme['BORDER']};
}}

/* 菜单样式 */
QMenuBar {{
    background-color: {theme['BG_DARKEST']};
    border-bottom: 0.5px solid {theme['BORDER_LIGHT']};
    font-size: {theme['FONT_SIZE']}px;
    padding: 2px 0px;
}}

QMenuBar::item {{
    background-color: transparent;
    padding: 6px 14px;
    border-radius: 6px;
    spacing: 4px;
}}

QMenuBar::item:selected {{
    background-color: {theme['BG_HOVER']};
}}

QMenu {{
    background-color: {theme['BG_CARD']};
    border: 0.5px solid {theme['BORDER']};
    border-radius: 10px;
    padding: 6px;
}}

QMenu::item {{
    padding: 8px 28px;
    border-radius: 6px;
    font-size: {theme['FONT_SIZE']}px;
}}

QMenu::item:selected {{
    background-color: {theme['PRIMARY']};
    color: white;
}}

/* 分割器样式 */
QSplitter::handle {{
    background-color: transparent;
}}

QSplitter::handle:horizontal {{
    width: 1px;
    background-color: {theme['BORDER_LIGHT']};
}}

QSplitter::handle:vertical {{
    height: 1px;
    background-color: {theme['BORDER_LIGHT']};
}}

QSplitter::handle:hover {{
    background-color: {theme['PRIMARY']};
}}

/* 自旋框样式 */
QSpinBox {{
    background-color: {theme['BG_INPUT']};
    color: {theme['TEXT_PRIMARY']};
    border: 1px solid transparent;
    border-radius: 8px;
    padding: 8px 12px;
    font-size: {theme['FONT_SIZE']}px;
}}

QSpinBox:focus {{
    border: 2px solid {theme['PRIMARY']};
    background-color: {theme['BG_CARD']};
}}

QSpinBox::up-button, QSpinBox::down-button {{
    background-color: transparent;
    border: none;
    width: 20px;
}}

QSpinBox::up-button:hover, QSpinBox::down-button:hover {{
    background-color: {theme['BG_HOVER']};
}}

/* 进度条样式 */
QProgressBar {{
    border: none;
    border-radius: 6px;
    background-color: {theme['BG_INPUT']};
    text-align: center;
    color: {theme['TEXT_PRIMARY']};
    font-size: 12px;
    height: 8px;
}}

QProgressBar::chunk {{
    background-color: {theme['PRIMARY']};
    border-radius: 6px;
}}
"""


# 生成默认样式表
STYLESHEET = generate_stylesheet()


# ==================== 数据模型 ====================
class SerialConfig:
    """串口配置数据类"""
    def __init__(self):
        self.port: str = ""
        self.baudrate: int = 115200
        self.databits: int = 8
        self.parity: str = "None"
        self.stopbits: float = 1.0
        self.flow_control: str = "None"
        
    def to_dict(self) -> dict:
        return {
            "port": self.port,
            "baudrate": self.baudrate,
            "databits": self.databits,
            "parity": self.parity,
            "stopbits": self.stopbits,
            "flow_control": self.flow_control
        }
    
    @classmethod
    def from_dict(cls, data: dict) -> "SerialConfig":
        config = cls()
        config.port = data.get("port", "")
        config.baudrate = data.get("baudrate", 115200)
        config.databits = data.get("databits", 8)
        config.parity = data.get("parity", "None")
        config.stopbits = data.get("stopbits", 1)
        config.flow_control = data.get("flow_control", "None")
        return config


# ==================== 串口工作线程 ====================
class SerialWorker(QThread):
    """串口通信后台线程"""
    data_received = pyqtSignal(bytes)
    connection_status = pyqtSignal(bool, str)
    error_occurred = pyqtSignal(str)
    
    def __init__(self):
        super().__init__()
        self.serial_port: Optional[serial.Serial] = None  # type: ignore
        self.config = SerialConfig()
        self._running = False
        self._send_queue: deque = deque()
        self._mutex = False
        
    def configure(self, config: SerialConfig):
        self.config = config
        
    def connect_port(self) -> bool:
        try:
            parity_map = {
                "None": serial.PARITY_NONE,  # type: ignore
                "Even": serial.PARITY_EVEN,  # type: ignore
                "Odd": serial.PARITY_ODD,  # type: ignore
                "Mark": serial.PARITY_MARK,  # type: ignore
                "Space": serial.PARITY_SPACE  # type: ignore
            }
            
            self.serial_port = serial.Serial(  # type: ignore
                port=self.config.port,
                baudrate=self.config.baudrate,
                bytesize=self.config.databits,
                parity=parity_map.get(self.config.parity, serial.PARITY_NONE),  # type: ignore
                stopbits=self.config.stopbits,
                timeout=0.1
            )
            
            self._running = True
            self.start()
            self.connection_status.emit(True, f"已连接到 {self.config.port}")
            return True
            
        except Exception as e:
            self.error_occurred.emit(f"连接失败: {str(e)}")
            return False
            
    def disconnect_port(self):
        self._running = False
        self.wait(1000)
        if self.serial_port and self.serial_port.is_open:
            self.serial_port.close()
        self.connection_status.emit(False, "已断开连接")
        
    def send_data(self, data: bytes):
        if self.serial_port and self.serial_port.is_open:
            try:
                self.serial_port.write(data)
                return True
            except Exception as e:
                self.error_occurred.emit(f"发送失败: {str(e)}")
        return False
        
    def run(self):
        while self._running:
            try:
                if self.serial_port and self.serial_port.in_waiting > 0:
                    data = self.serial_port.read(self.serial_port.in_waiting)
                    if data:
                        self.data_received.emit(data)
            except Exception as e:
                self.error_occurred.emit(f"读取错误: {str(e)}")
                break
            self.msleep(10)


# ==================== 自定义控件 ====================
class Card(QFrame):
    """macOS 风格卡片容器控件"""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("card")
        self.setFrameShape(QFrame.Shape.StyledPanel)
        
        # macOS 风格的柔和阴影
        shadow = QGraphicsDropShadowEffect(self)
        shadow.setBlurRadius(30)
        shadow.setColor(QColor(0, 0, 0, 15))
        shadow.setOffset(0, 2)
        self.setGraphicsEffect(shadow)
        
        self._layout = QVBoxLayout(self)
        self._layout.setContentsMargins(20, 20, 20, 20)
        self._layout.setSpacing(16)


class StatusIndicator(QLabel):
    """macOS 风格状态指示器"""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedSize(10, 10)
        self.set_connected(False)
        
    def set_connected(self, connected: bool):
        theme = ThemeManager.get_theme()
        color = theme['SUCCESS'] if connected else theme['TEXT_MUTED']
        self.setStyleSheet(f"""
            QLabel {{
                background-color: {color};
                border-radius: 5px;
                border: 2px solid white;
            }}
        """)


class ModernButton(QPushButton):
    """现代风格按钮"""
    def __init__(self, text: str, variant: str = "default", parent=None):
        super().__init__(text, parent)
        self.setObjectName(variant)
        self.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        
        # 添加悬停动画
        self._animation = QPropertyAnimation(self, b"geometry")  # type: ignore
        self._animation.setDuration(150)
        self._animation.setEasingCurve(QEasingCurve.Type.OutCubic)


class ModernComboBox(QComboBox):
    """现代风格下拉框"""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimumHeight(36)
        self.view().setMinimumWidth(120)


class ModernLineEdit(QLineEdit):
    """现代风格输入框"""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimumHeight(36)


# ==================== 主窗口 ====================
class SerialDebugTool(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Serial Studio")
        self.setMinimumSize(1200, 800)
        
        # macOS 风格窗口设置
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint | Qt.WindowType.WindowSystemMenuHint | Qt.WindowType.WindowMinimizeButtonHint | Qt.WindowType.WindowMaximizeButtonHint)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        
        # 初始化组件
        self.serial_worker = SerialWorker()
        self.settings = QSettings("SerialStudio", "Config")
        
        # 历史记录
        self.send_history: List[str] = []
        self.max_history = 50
        
        self._setup_ui()
        self._setup_connections()
        self._load_settings()
        self._scan_ports()
        
        # 定时刷新串口列表
        self.port_timer = QTimer(self)
        self.port_timer.timeout.connect(self._scan_ports)
        self.port_timer.start(2000)
        
    def _setup_ui(self):
        """构建UI"""
        main_container = QWidget()
        main_container.setObjectName("mainContainer")
        main_container.setStyleSheet("""
            QWidget#mainContainer {
                background-color: white;
                border-radius: 12px;
            }
        """)
        
        main_layout = QVBoxLayout(main_container)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)
        
        # macOS 风格标题栏
        title_bar = self._create_macos_titlebar()
        main_layout.addWidget(title_bar)
        
        # 内容区域
        content_widget = QWidget()
        content_layout = QHBoxLayout(content_widget)
        content_layout.setContentsMargins(24, 20, 24, 20)
        content_layout.setSpacing(20)
        
        # 左侧控制面板
        left_panel = self._create_control_panel()
        
        # 中间数据区域
        center_panel = self._create_data_panel()
        
        # 右侧辅助面板
        right_panel = self._create_aux_panel()
        
        # 使用分割器
        splitter = QSplitter(Qt.Orientation.Horizontal)
        splitter.addWidget(left_panel)
        splitter.addWidget(center_panel)
        splitter.addWidget(right_panel)
        splitter.setSizes([300, 650, 220])
        splitter.setHandleWidth(1)
        
        content_layout.addWidget(splitter)
        main_layout.addWidget(content_widget, 1)
        
        self.setCentralWidget(main_container)
        
        # 状态栏
        self._setup_statusbar()
        self._setup_menubar()
        
    def _create_macos_titlebar(self) -> QWidget:
        """创建 macOS 风格标题栏"""
        title_bar = QFrame()
        title_bar.setFixedHeight(52)
        theme = ThemeManager.get_theme()
        title_bar.setStyleSheet(f"""
            QFrame {{
                background-color: {theme['BG_DARKEST']};
                border-bottom: 0.5px solid {theme['BORDER_LIGHT']};
                border-top-left-radius: 12px;
                border-top-right-radius: 12px;
            }}
        """)
        
        layout = QHBoxLayout(title_bar)
        layout.setContentsMargins(16, 8, 16, 8)
        layout.setSpacing(12)
        
        # 窗口控制按钮（红黄绿）
        buttons_layout = QHBoxLayout()
        buttons_layout.setSpacing(8)
        
        close_btn = QPushButton()
        close_btn.setFixedSize(14, 14)
        close_btn.setStyleSheet("""
            QPushButton {
                background-color: #FF5F57;
                border-radius: 7px;
                border: none;
            }
            QPushButton:hover {
                background-color: #FF3B30;
            }
        """)
        close_btn.clicked.connect(lambda: self.close())  # type: ignore
        buttons_layout.addWidget(close_btn)
        
        minimize_btn = QPushButton()
        minimize_btn.setFixedSize(14, 14)
        minimize_btn.setStyleSheet("""
            QPushButton {
                background-color: #FFBD2E;
                border-radius: 7px;
                border: none;
            }
            QPushButton:hover {
                background-color: #FF9500;
            }
        """)
        minimize_btn.clicked.connect(self.showMinimized)
        buttons_layout.addWidget(minimize_btn)
        
        maximize_btn = QPushButton()
        maximize_btn.setFixedSize(14, 14)
        maximize_btn.setStyleSheet("""
            QPushButton {
                background-color: #28C840;
                border-radius: 7px;
                border: none;
            }
            QPushButton:hover {
                background-color: #34C759;
            }
        """)
        maximize_btn.clicked.connect(self._toggle_maximize)
        buttons_layout.addWidget(maximize_btn)
        
        layout.addLayout(buttons_layout)
        
        # 标题
        title_label = QLabel("Serial Studio")
        title_label.setStyleSheet(f"""
            QLabel {{
                color: {theme['TEXT_PRIMARY']};
                font-size: 14px;
                font-weight: 600;
            }}
        """)
        title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(title_label, 1)
        
        # 主题切换下拉框
        theme_combo = QComboBox()
        theme_combo.setMinimumWidth(140)
        theme_combo.addItems([ThemeManager.THEMES[t]["name"] for t in ThemeManager.get_theme_list()])
        
        # 设置当前主题
        current_index = theme_combo.findText(ThemeManager.THEMES[ThemeManager.current_theme]["name"])
        if current_index >= 0:
            theme_combo.setCurrentIndex(current_index)
        
        theme_combo.currentIndexChanged.connect(self._on_theme_changed)
        layout.addWidget(theme_combo)
        
        return title_bar
    
    def _on_theme_changed(self, index):
        """主题切换事件"""
        theme_keys = ThemeManager.get_theme_list()
        if 0 <= index < len(theme_keys):
            new_theme = theme_keys[index]
            self._switch_to_theme(new_theme)
    
    def _switch_to_theme(self, theme_name):
        """切换到指定主题"""
        # 切换主题
        ThemeManager.switch_theme(theme_name)
        
        # 重新生成样式表并应用
        new_stylesheet = generate_stylesheet(theme_name)
        self.setStyleSheet(new_stylesheet)
        
        # 重新应用主题（更新调色板和字体）
        ThemeManager.apply(QApplication.instance())  # type: ignore
        
        # 刷新标题栏
        old_titlebar = self.centralWidget().layout().itemAt(0).widget()
        if old_titlebar:
            old_titlebar.deleteLater()
        
        new_titlebar = self._create_macos_titlebar()
        # 使用 insertWidget 的正确方式
        main_layout = self.centralWidget().layout()
        if isinstance(main_layout, QVBoxLayout):
            main_layout.insertWidget(0, new_titlebar)
        
        # 显示提示
        theme_info = ThemeManager.THEMES[theme_name]
        self.statusbar.showMessage(f"已切换到 {theme_info['name']} 主题", 2000)
    
    def _toggle_maximize(self):
        """切换最大化/还原窗口"""
        if self.isMaximized():
            self.showNormal()
        else:
            self.showMaximized()
    
    def mousePressEvent(self, a0):  # type: ignore
        """鼠标按下事件 - 用于拖动窗口"""
        if a0.button() == Qt.MouseButton.LeftButton:
            global_pos = a0.globalPosition().toPoint()
            window_pos = self.pos()
            self._drag_pos = QPoint(global_pos.x() - window_pos.x(), global_pos.y() - window_pos.y())
            a0.accept()
    
    def mouseMoveEvent(self, a0):  # type: ignore
        """鼠标移动事件 - 用于拖动窗口"""
        if a0.buttons() == Qt.MouseButton.LeftButton and hasattr(self, '_drag_pos'):
            global_pos = a0.globalPosition().toPoint()
            new_pos = QPoint(global_pos.x() - self._drag_pos.x(), global_pos.y() - self._drag_pos.y())
            self.move(new_pos)
            a0.accept()
        
    def _create_control_panel(self) -> QWidget:
        """创建左侧控制面板"""
        container = QWidget()
        layout = QVBoxLayout(container)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(16)
        
        # 连接设置卡片
        conn_card = Card()
        conn_layout = conn_card._layout
        
        title = QLabel("连接设置")
        title.setObjectName("title")
        conn_layout.addWidget(title)
        
        # 串口选择
        port_layout = QHBoxLayout()
        port_layout.addWidget(QLabel("串口"))
        self.port_combo = ModernComboBox()
        self.port_combo.setMinimumWidth(150)
        port_layout.addWidget(self.port_combo, 1)
        
        refresh_btn = QToolButton()
        refresh_btn.setText("↻")
        refresh_btn.setToolTip("刷新串口列表")
        refresh_btn.clicked.connect(self._scan_ports)
        port_layout.addWidget(refresh_btn)
        conn_layout.addLayout(port_layout)
        
        # 波特率
        baud_layout = QHBoxLayout()
        baud_layout.addWidget(QLabel("波特率"))
        self.baud_combo = ModernComboBox()
        baud_rates = ["9600", "19200", "38400", "57600", "115200", "230400", "460800", "921600"]
        self.baud_combo.addItems(baud_rates)
        self.baud_combo.setCurrentText("115200")
        self.baud_combo.setEditable(True)
        baud_layout.addWidget(self.baud_combo)
        conn_layout.addLayout(baud_layout)
        
        # 数据位、校验、停止位
        grid = QGridLayout()
        grid.setSpacing(8)
        
        grid.addWidget(QLabel("数据位"), 0, 0)
        self.databits_combo = ModernComboBox()
        self.databits_combo.addItems(["7", "8"])
        self.databits_combo.setCurrentText("8")
        grid.addWidget(self.databits_combo, 0, 1)
        
        grid.addWidget(QLabel("校验"), 1, 0)
        self.parity_combo = ModernComboBox()
        self.parity_combo.addItems(["None", "Even", "Odd", "Mark", "Space"])
        grid.addWidget(self.parity_combo, 1, 1)
        
        grid.addWidget(QLabel("停止位"), 2, 0)
        self.stopbits_combo = ModernComboBox()
        self.stopbits_combo.addItems(["1", "1.5", "2"])
        grid.addWidget(self.stopbits_combo, 2, 1)
        
        conn_layout.addLayout(grid)
        
        # 连接按钮
        self.connect_btn = ModernButton("连接串口", "primary")
        self.connect_btn.setMinimumHeight(44)
        self.connect_btn.clicked.connect(self._toggle_connection)
        conn_layout.addWidget(self.connect_btn)
        
        layout.addWidget(conn_card)
        
        # 发送设置卡片
        send_card = Card()
        send_layout = send_card._layout
        
        send_title = QLabel("发送设置")
        send_title.setObjectName("title")
        send_layout.addWidget(send_title)
        
        # 发送选项
        self.hex_send_check = QCheckBox("Hex 发送")
        send_layout.addWidget(self.hex_send_check)
        
        self.auto_newline_check = QCheckBox("自动添加换行 (\\n)")
        self.auto_newline_check.setChecked(True)
        send_layout.addWidget(self.auto_newline_check)
        
        self.repeat_send_check = QCheckBox("定时发送")
        send_layout.addWidget(self.repeat_send_check)
        
        repeat_layout = QHBoxLayout()
        repeat_layout.addWidget(QLabel("间隔 (ms):"))
        self.repeat_spin = QSpinBox()
        self.repeat_spin.setRange(10, 99999)
        self.repeat_spin.setValue(1000)
        self.repeat_spin.setEnabled(False)
        repeat_layout.addWidget(self.repeat_spin)
        send_layout.addLayout(repeat_layout)
        
        self.repeat_send_check.toggled.connect(self.repeat_spin.setEnabled)
        
        layout.addWidget(send_card)
        
        # 接收设置卡片
        recv_card = Card()
        recv_layout = recv_card._layout
        
        recv_title = QLabel("接收设置")
        recv_title.setObjectName("title")
        recv_layout.addWidget(recv_title)
        
        self.hex_recv_check = QCheckBox("Hex 显示")
        recv_layout.addWidget(self.hex_recv_check)
        
        self.timestamp_check = QCheckBox("显示时间戳")
        recv_layout.addWidget(self.timestamp_check)
        
        self.pause_recv_check = QCheckBox("暂停接收")
        recv_layout.addWidget(self.pause_recv_check)
        
        self.log_file_check = QCheckBox("保存到文件")
        recv_layout.addWidget(self.log_file_check)
        
        btn_layout = QHBoxLayout()
        clear_btn = ModernButton("清空接收区")
        clear_btn.clicked.connect(self._clear_receive)
        btn_layout.addWidget(clear_btn)
        
        save_btn = ModernButton("保存数据")
        save_btn.clicked.connect(self._save_data)
        btn_layout.addWidget(save_btn)
        recv_layout.addLayout(btn_layout)
        
        layout.addWidget(recv_card)
        layout.addStretch()
        
        return container
        
    def _create_data_panel(self) -> QWidget:
        """创建中间数据面板"""
        container = QWidget()
        layout = QVBoxLayout(container)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(16)
        
        # 接收区
        recv_card = Card()
        recv_layout = recv_card._layout
        
        recv_header = QHBoxLayout()
        recv_title = QLabel("数据接收")
        recv_title.setObjectName("title")
        recv_header.addWidget(recv_title)
        
        self.status_indicator = StatusIndicator()
        recv_header.addWidget(self.status_indicator)
        
        self.status_label = QLabel("未连接")
        self.status_label.setObjectName("status_disconnected")
        recv_header.addWidget(self.status_label)
        recv_header.addStretch()
        
        self.rx_count_label = QLabel("RX: 0 bytes")
        self.rx_count_label.setObjectName("subtitle")
        recv_header.addWidget(self.rx_count_label)
        
        recv_layout.addLayout(recv_header)
        
        self.receive_text = QTextEdit()
        self.receive_text.setReadOnly(True)
        self.receive_text.setMinimumHeight(400)
        self.receive_text.setPlaceholderText("接收到的数据将显示在这里...")
        recv_layout.addWidget(self.receive_text)
        
        layout.addWidget(recv_card, 1)
        
        # 发送区
        send_card = Card()
        send_layout = send_card._layout
        
        send_header = QHBoxLayout()
        send_title = QLabel("数据发送")
        send_title.setObjectName("title")
        send_header.addWidget(send_title)
        
        self.tx_count_label = QLabel("TX: 0 bytes")
        self.tx_count_label.setObjectName("subtitle")
        send_header.addWidget(self.tx_count_label)
        send_header.addStretch()
        
        history_btn = QToolButton()
        history_btn.setText("历史")
        history_btn.setToolTip("发送历史")
        history_btn.clicked.connect(self._show_history)
        send_header.addWidget(history_btn)
        
        send_layout.addLayout(send_header)
        
        self.send_input = ModernLineEdit()
        self.send_input.setPlaceholderText("输入要发送的数据...")
        self.send_input.returnPressed.connect(self._send_data)
        send_layout.addWidget(self.send_input)
        
        send_btn_layout = QHBoxLayout()
        self.send_btn = ModernButton("发送", "primary")
        self.send_btn.setMinimumHeight(40)
        self.send_btn.clicked.connect(self._send_data)
        self.send_btn.setEnabled(False)
        send_btn_layout.addWidget(self.send_btn)
        
        quick_send_btn = ModernButton("快速发送")
        quick_send_btn.clicked.connect(self._quick_send)
        send_btn_layout.addWidget(quick_send_btn)
        
        send_layout.addLayout(send_btn_layout)
        layout.addWidget(send_card)
        
        return container
        
    def _create_aux_panel(self) -> QWidget:
        """创建右侧辅助面板"""
        container = QWidget()
        layout = QVBoxLayout(container)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(16)
        
        # 快捷发送
        quick_card = Card()
        quick_layout = quick_card._layout
        
        quick_title = QLabel("快捷指令")
        quick_title.setObjectName("title")
        quick_layout.addWidget(quick_title)
        
        self.quick_list = QTextEdit()
        self.quick_list.setMaximumHeight(200)
        self.quick_list.setPlaceholderText("每行一个快捷指令...")
        quick_layout.addWidget(self.quick_list)
        
        add_quick_btn = ModernButton("添加到快捷栏")
        add_quick_btn.clicked.connect(self._add_quick_command)
        quick_layout.addWidget(add_quick_btn)
        
        layout.addWidget(quick_card)
        
        # 统计信息
        stats_card = Card()
        stats_layout = stats_card._layout
        
        stats_title = QLabel("统计信息")
        stats_title.setObjectName("title")
        stats_layout.addWidget(stats_title)
        
        self.stats_text = QTextEdit()
        self.stats_text.setReadOnly(True)
        self.stats_text.setMaximumHeight(150)
        stats_layout.addWidget(self.stats_text)
        
        reset_stats_btn = ModernButton("重置统计")
        reset_stats_btn.clicked.connect(self._reset_stats)
        stats_layout.addWidget(reset_stats_btn)
        
        layout.addWidget(stats_card)
        layout.addStretch()
        
        return container
        
    def _setup_statusbar(self):
        """设置状态栏"""
        self.statusbar = QStatusBar()
        self.setStatusBar(self.statusbar)
        self.statusbar.showMessage("就绪")
        
    def _setup_menubar(self):
        """设置菜单栏"""
        menubar = self.menuBar()
        
        file_menu = menubar.addMenu("文件")
        file_menu.addAction("导出配置", self._export_config)
        file_menu.addAction("导入配置", self._import_config)
        file_menu.addSeparator()
        file_menu.addAction("退出", lambda: self.close())  # type: ignore
        
        tools_menu = menubar.addMenu("工具")
        tools_menu.addAction("计算器", self._open_calculator)
        tools_menu.addAction("ASCII 表", self._open_ascii_table)
        
        help_menu = menubar.addMenu("帮助")
        help_menu.addAction("关于", self._show_about)
        
    def _setup_toolbar(self):
        """设置工具栏"""
        toolbar = QToolBar()
        toolbar.setMovable(False)
        toolbar.setFloatable(False)
        self.addToolBar(toolbar)
        
    def _setup_connections(self):
        """设置信号连接"""
        self.serial_worker.data_received.connect(self._on_data_received)
        self.serial_worker.connection_status.connect(self._on_connection_status)
        self.serial_worker.error_occurred.connect(self._on_error)
        
        # 定时发送定时器
        self.repeat_timer = QTimer(self)
        self.repeat_timer.timeout.connect(self._send_data)
        
    def _scan_ports(self):
        """扫描可用串口"""
        current = self.port_combo.currentText()
        self.port_combo.clear()
        
        ports = serial.tools.list_ports.comports()
        for port in ports:
            self.port_combo.addItem(f"{port.device} - {port.description}", port.device)
            
        # 恢复之前的选择
        index = self.port_combo.findText(current)
        if index >= 0:
            self.port_combo.setCurrentIndex(index)
            
    def _toggle_connection(self):
        """切换连接状态"""
        if self.serial_worker.isRunning():
            self.serial_worker.disconnect_port()
            self.repeat_timer.stop()
        else:
            config = SerialConfig()
            config.port = self.port_combo.currentData() or self.port_combo.currentText().split(" - ")[0]
            config.baudrate = int(self.baud_combo.currentText())
            config.databits = int(self.databits_combo.currentText())
            config.parity = self.parity_combo.currentText()
            config.stopbits = float(self.stopbits_combo.currentText())
            
            self.serial_worker.configure(config)
            if self.serial_worker.connect_port():
                if self.repeat_send_check.isChecked():
                    self.repeat_timer.start(self.repeat_spin.value())
                    
    def _send_data(self):
        """发送数据"""
        text = self.send_input.text()
        if not text:
            return
            
        # 添加到历史
        if text not in self.send_history:
            self.send_history.insert(0, text)
            if len(self.send_history) > self.max_history:
                self.send_history.pop()
        
        # 处理数据
        if self.hex_send_check.isChecked():
            try:
                data = bytes.fromhex(text.replace(" ", ""))
            except ValueError:
                self._on_error("无效的十六进制数据")
                return
        else:
            data = text.encode("utf-8")
            if self.auto_newline_check.isChecked():
                data += b"\n"
                
        if self.serial_worker.send_data(data):
            self._update_tx_count(len(data))
            self.send_input.clear()
            
    def _on_data_received(self, data: bytes):
        """处理接收到的数据"""
        if self.pause_recv_check.isChecked():
            return
            
        if self.hex_recv_check.isChecked():
            text = " ".join(f"{b:02X}" for b in data)
        else:
            try:
                text = data.decode("utf-8", errors="replace")
            except:
                text = " ".join(f"{b:02X}" for b in data)
                
        if self.timestamp_check.isChecked():
            timestamp = datetime.now().strftime("%H:%M:%S.%f")[:-3]
            text = f"[{timestamp}] {text}"
            
        self.receive_text.append(text)
        self._update_rx_count(len(data))
        
        # 限制缓冲区大小
        if self.receive_text.document().characterCount() > 100000:
            cursor = self.receive_text.textCursor()
            cursor.movePosition(cursor.MoveOperation.Start)
            cursor.select(cursor.SelectionType.BlockUnderCursor)
            cursor.removeSelectedText()
            
    def _on_connection_status(self, connected: bool, message: str):
        """处理连接状态变化"""
        self.status_indicator.set_connected(connected)
        self.status_label.setText(message)
        self.status_label.setObjectName("status_connected" if connected else "status_disconnected")
        self.status_label.style().unpolish(self.status_label)
        self.status_label.style().polish(self.status_label)
        
        self.connect_btn.setText("断开连接" if connected else "连接串口")
        self.connect_btn.setObjectName("danger" if connected else "primary")
        self.connect_btn.style().unpolish(self.connect_btn)
        self.connect_btn.style().polish(self.connect_btn)
        
        self.send_btn.setEnabled(connected)
        self.port_combo.setEnabled(not connected)
        
        self.statusbar.showMessage(message, 3000)
        
    def _on_error(self, message: str):
        """处理错误"""
        self.statusbar.showMessage(message, 5000)
        # 可以添加错误提示动画或通知
        
    def _clear_receive(self):
        """清空接收区"""
        self.receive_text.clear()
        
    def _save_data(self):
        """保存接收的数据"""
        filename, _ = QFileDialog.getSaveFileName(
            self, "保存数据", "", "文本文件 (*.txt);;所有文件 (*)"
        )
        if filename:
            with open(filename, "w", encoding="utf-8") as f:
                f.write(self.receive_text.toPlainText())
            self.statusbar.showMessage(f"数据已保存到 {filename}", 3000)
            
    def _quick_send(self):
        """快速发送"""
        dialog = QDialog(self)
        dialog.setWindowTitle("快速发送")
        dialog.setMinimumWidth(300)
        
        layout = QVBoxLayout(dialog)
        text_edit = QTextEdit()
        text_edit.setPlaceholderText("输入多行数据，每行将分别发送...")
        layout.addWidget(text_edit)
        
        btn = ModernButton("发送", "primary")
        btn.clicked.connect(dialog.accept)
        layout.addWidget(btn)
        
        if dialog.exec() == QDialog.DialogCode.Accepted:
            lines = text_edit.toPlainText().strip().split("\n")
            for line in lines:
                if line:
                    self.send_input.setText(line)
                    self._send_data()
                    
    def _show_history(self):
        """显示发送历史"""
        if not self.send_history:
            return
            
        menu = QMenu(self)
        for item in self.send_history[:10]:
            action = menu.addAction(item[:50])
            action.triggered.connect(lambda checked, t=item: self.send_input.setText(t))
        sender_widget = self.sender()  # type: ignore
        if sender_widget:
            menu.exec(sender_widget.mapToGlobal(QPoint(0, sender_widget.height())))  # type: ignore
            
    def _add_quick_command(self):
        """添加快捷命令"""
        text = self.send_input.text()
        if text:
            current = self.quick_list.toPlainText()
            if current:
                current += "\n"
            self.quick_list.setPlainText(current + text)
            
    def _reset_stats(self):
        """重置统计"""
        self.rx_count = 0
        self.tx_count = 0
        self.rx_count_label.setText("RX: 0 bytes")
        self.tx_count_label.setText("TX: 0 bytes")
        self.stats_text.clear()
        
    def _update_rx_count(self, count: int):
        """更新接收计数"""
        if not hasattr(self, 'rx_count'):
            self.rx_count = 0
        self.rx_count += count
        self.rx_count_label.setText(f"RX: {self.rx_count} bytes")
        
    def _update_tx_count(self, count: int):
        """更新发送计数"""
        if not hasattr(self, 'tx_count'):
            self.tx_count = 0
        self.tx_count += count
        self.tx_count_label.setText(f"TX: {self.tx_count} bytes")
        
    def _export_config(self):
        """导出配置"""
        filename, _ = QFileDialog.getSaveFileName(
            self, "导出配置", "serial_config.json", "JSON (*.json)"
        )
        if filename:
            config = {
                "port": self.port_combo.currentText(),
                "baudrate": self.baud_combo.currentText(),
                "databits": self.databits_combo.currentText(),
                "parity": self.parity_combo.currentText(),
                "stopbits": self.stopbits_combo.currentText(),
                "hex_send": self.hex_send_check.isChecked(),
                "hex_recv": self.hex_recv_check.isChecked(),
                "auto_newline": self.auto_newline_check.isChecked(),
                "timestamp": self.timestamp_check.isChecked()
            }
            with open(filename, "w", encoding="utf-8") as f:
                json.dump(config, f, indent=2)
                
    def _import_config(self):
        """导入配置"""
        filename, _ = QFileDialog.getOpenFileName(
            self, "导入配置", "", "JSON (*.json)"
        )
        if filename:
            try:
                with open(filename, "r", encoding="utf-8") as f:
                    config = json.load(f)
                self.baud_combo.setCurrentText(config.get("baudrate", "115200"))
                self.databits_combo.setCurrentText(config.get("databits", "8"))
                self.parity_combo.setCurrentText(config.get("parity", "None"))
                self.stopbits_combo.setCurrentText(config.get("stopbits", "1"))
                self.hex_send_check.setChecked(config.get("hex_send", False))
                self.hex_recv_check.setChecked(config.get("hex_recv", False))
                self.auto_newline_check.setChecked(config.get("auto_newline", True))
                self.timestamp_check.setChecked(config.get("timestamp", False))
            except Exception as e:
                QMessageBox.critical(self, "错误", f"导入失败: {str(e)}")
                
    def _open_calculator(self):
        """打开计算器"""
        # 可以实现内置计算器或调用系统计算器
        pass
        
    def _open_ascii_table(self):
        """打开ASCII表"""
        dialog = QDialog(self)
        dialog.setWindowTitle("ASCII 表")
        dialog.setMinimumSize(600, 400)
        
        layout = QVBoxLayout(dialog)
        text = QTextEdit()
        text.setReadOnly(True)
        
        ascii_table = ""
        for i in range(0, 128, 16):
            row = ""
            for j in range(16):
                c = i + j
                if c < 32:
                    char = f"[{['NUL','SOH','STX','ETX','EOT','ENQ','ACK','BEL','BS','TAB','LF','VT','FF','CR','SO','SI','DLE','DC1','DC2','DC3','DC4','NAK','SYN','ETB','CAN','EM','SUB','ESC','FS','GS','RS','US'][c]}]"
                elif c == 127:
                    char = "[DEL]"
                else:
                    char = chr(c)
                row += f"{c:3d} 0x{c:02X} {char:6}  "
            ascii_table += row + "\n"
            
        text.setPlainText(ascii_table)
        layout.addWidget(text)
        dialog.exec()
        
    def _show_about(self):
        """显示关于对话框"""
        QMessageBox.about(
            self,
            "关于 Serial Studio",
            "<h2>Serial Studio v1.0</h2>"
            "<p>现代化的串口调试工具</p>"
            "<p>基于 PyQt6 构建</p>"
        )
        
    def _load_settings(self):
        """加载设置"""
        self.settings.beginGroup("MainWindow")
        self.resize(self.settings.value("size", QSize(1200, 800)))
        self.move(self.settings.value("pos", QPoint(100, 100)))
        self.settings.endGroup()
        
    def closeEvent(self, a0):  # type: ignore
        """关闭事件"""
        self.settings.beginGroup("MainWindow")
        self.settings.setValue("size", self.size())
        self.settings.setValue("pos", self.pos())
        self.settings.endGroup()
        
        if self.serial_worker.isRunning():
            self.serial_worker.disconnect_port()
        a0.accept()  # type: ignore


def main():
    app = QApplication(sys.argv)
    
    # 启用高 DPI 缩放
    app.setHighDpiScaleFactorRoundingPolicy(Qt.HighDpiScaleFactorRoundingPolicy.PassThrough)
    
    # 应用默认主题
    ThemeManager.apply(app)
    app.setStyleSheet(STYLESHEET)
    
    window = SerialDebugTool()
    window.show()
    
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
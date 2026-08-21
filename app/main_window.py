from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QPushButton, QFrame, QSplitter, QTextEdit, QMessageBox, QFileDialog, QMenuBar, QMenu, QScrollArea, QGridLayout, QStackedWidget, QComboBox
)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QFont, QIcon
import sys
import os

from app.pages.home_page import HomePage
from app.pages.serial_debug_page import SerialDebugPage
from app.pages.placeholder_page import PlaceholderPage
from app.pages.resistor_color_code_page import ResistorColorCodePage
from app.pages.power_conversion_page import PowerConversionPage
from app.pages.programming_software_page import ProgrammingSoftwarePage
from app.pages.text_polish_page import TextPolishPage


class SerialDebugTool(QMainWindow):
    def __init__(self):
        super().__init__()
        self.initUI()
        # 不在此处 show(): 窗口显示与构造分离, 由 main() 显式控制

    def initUI(self):
        # 设置窗口基本属性
        self.setWindowTitle('串口调试工具')
        from app.core.config_manager import app_root
        icon_path = str(app_root() / "assets" / "icon.png")
        if os.path.exists(icon_path):
            self.setWindowIcon(QIcon(icon_path))
        self.setGeometry(100, 100, 1200, 800)
        
        # 记录导航栏状态
        self.nav_expanded = True  # True=展开, False=收起
        
        # 创建中央部件
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        
        # 主布局
        main_layout = QHBoxLayout(central_widget)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)
        
        # ===== 左侧导航栏 =====
        nav_frame = QFrame()
        nav_frame.setObjectName("navFrame")
        nav_frame.setFixedWidth(200)
        self.nav_frame = nav_frame  # 保存引用以便后续修改宽度
        nav_layout = QVBoxLayout(nav_frame)
        nav_layout.setContentsMargins(10, 20, 10, 20)
        nav_layout.setSpacing(5)
        
        # 标题栏(带切换按钮)
        title_layout = QHBoxLayout()
        
        self.title_label = QLabel("⚡ 工作助手")
        self.title_label.setFont(QFont("Microsoft YaHei", 16, QFont.Weight.Bold))
        self.title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.title_label.setStyleSheet("color: #333; padding: 10px;")
        title_layout.addWidget(self.title_label)
        
        # 切换按钮
        toggle_btn = QPushButton("◀")
        toggle_btn.setFixedSize(30, 30)
        toggle_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        toggle_btn.setStyleSheet("""
            QPushButton {
                background: transparent;
                color: #999;
                border: none;
                border-radius: 15px;
                font-size: 14px;
            }
            QPushButton:hover {
                background: #E8F4FF;
                color: #409EFF;
            }
        """)
        toggle_btn.clicked.connect(self.toggle_nav_bar)
        self.toggle_btn = toggle_btn  # 保存引用, 避免通过布局索引反查
        title_layout.addWidget(toggle_btn)
        
        nav_layout.addLayout(title_layout)
        
        nav_layout.addSpacing(20)
        
        # 保存导航项数据
        self.nav_items = [
            ("🏠", "首页概览"),
            ("🔌", "串口调试"),
            ("📄", "文本润色"),
            ("💾", "烧录软件"),
            ("📈", "功率变换"),
            ("📚", "常识查询"),
            ("⚙️", "系统设置")
        ]
        
        # 导航按钮列表
        self.nav_buttons = []
        for index, (icon, text) in enumerate(self.nav_items):
            btn = self.create_nav_button(icon, text, index)
            nav_layout.addWidget(btn)
            self.nav_buttons.append(btn)
        
        nav_layout.addStretch()
        
        # ===== 右侧内容区 - 使用堆叠窗口 =====
        content_widget = QWidget()
        content_layout = QVBoxLayout(content_widget)
        content_layout.setContentsMargins(20, 20, 20, 20)
        content_layout.setSpacing(20)
        
        # 堆叠窗口 - 用于切换不同页面
        self.stacked_widget = QStackedWidget()
        
        # 页面工厂 (懒加载: 首次切换时才创建, 加快启动速度)
        self._page_factories = [
            lambda: HomePage(),
            lambda: SerialDebugPage(),
            lambda: TextPolishPage(),
            lambda: ProgrammingSoftwarePage(),
            lambda: PowerConversionPage(),
            lambda: ResistorColorCodePage(),
            lambda: PlaceholderPage("系统设置", "⚙️"),
        ]
        self._pages: dict = {}

        # 启动时只创建默认页 (首页)
        self._ensure_page(0)
        
        content_layout.addWidget(self.stacked_widget)
        
        # 添加到主布局
        main_layout.addWidget(nav_frame)
        main_layout.addWidget(content_widget, 1)
        
        # 默认选中首页
        self.nav_buttons[0].setChecked(True)
        
        # 应用样式
        self.apply_styles()
    
    def create_nav_button(self, icon, text, index):
        """创建导航按钮"""
        btn = QPushButton(f"{icon}  {text}")
        btn.setMinimumHeight(50)
        btn.setFont(QFont("Microsoft YaHei", 11))
        btn.setCursor(Qt.CursorShape.PointingHandCursor)
        btn.setProperty("index", index)  # 保存页面索引
        btn.setStyleSheet("""
            QPushButton {
                background: transparent;
                color: #555;
                border: none;
                border-radius: 8px;
                text-align: left;
                padding-left: 15px;
                padding-right: 15px;
            }
            QPushButton:hover {
                background: #E8F4FF;
                color: #409EFF;
            }
            QPushButton:checked {
                background: #409EFF;
                color: white;
            }
        """)
        btn.setCheckable(True)
        btn.clicked.connect(lambda: self.switch_page(index))
        return btn
    
    def switch_page(self, index):
        """切换页面"""
        # 取消其他按钮的选中状态
        for i, btn in enumerate(self.nav_buttons):
            if i != index:
                btn.setChecked(False)
        
        # 懒加载: 首次访问才创建页面, 按对象切换 (不依赖堆叠索引, 避免错位)
        page = self._ensure_page(index)
        self.stacked_widget.setCurrentWidget(page)
    
    def _ensure_page(self, index):
        """按需创建页面 (懒加载)"""
        if index not in self._pages:
            self._pages[index] = self._page_factories[index]()
            self.stacked_widget.addWidget(self._pages[index])
        return self._pages[index]
    
    def toggle_nav_bar(self):
        """切换导航栏展开/收起状态"""
        self.nav_expanded = not self.nav_expanded

        if self.nav_expanded:
            # 展开模式
            self.nav_frame.setFixedWidth(200)
            self.title_label.setText("⚡ 工作助手")
            self.toggle_btn.setText("◀")

            # 更新按钮显示文字
            for btn, (icon, text) in zip(self.nav_buttons, self.nav_items):
                btn.setText(f"{icon}  {text}")
        else:
            # 收起模式(只显示图标)
            self.nav_frame.setFixedWidth(70)
            self.title_label.setText("⚡")
            self.toggle_btn.setText("▶")

            # 更新按钮只显示图标
            for btn, (icon, text) in zip(self.nav_buttons, self.nav_items):
                btn.setText(f"{icon}")
    
    def create_card(self, title, value, icon, color):
        """创建信息卡片"""
        card = QFrame()
        card.setObjectName("card")
        card.setFixedHeight(120)
        card.setStyleSheet(f"""
            QFrame#card {{
                background: white;
                border-radius: 8px;
                border-left: 4px solid {color};
            }}
            QFrame#card:hover {{
                background: #F5F7FA;
            }}
        """)
        
        layout = QVBoxLayout(card)
        layout.setContentsMargins(20, 15, 20, 15)
        layout.setSpacing(8)
        
        # 图标和标题行
        top_layout = QHBoxLayout()
        icon_label = QLabel(icon)
        icon_label.setFont(QFont("Microsoft YaHei", 20))
        top_layout.addWidget(icon_label)
        
        title_label = QLabel(title)
        title_label.setFont(QFont("Microsoft YaHei", 12))
        title_label.setStyleSheet("color: #666;")
        top_layout.addWidget(title_label)
        top_layout.addStretch()
        layout.addLayout(top_layout)
        
        # 数值
        value_label = QLabel(value)
        value_label.setFont(QFont("Microsoft YaHei", 18, QFont.Weight.Bold))
        value_label.setStyleSheet(f"color: {color};")
        layout.addWidget(value_label)
        
        return card
    
    def apply_styles(self):
        """应用全局样式"""
        self.setStyleSheet("""
            QMainWindow {
                background: #F5F7FA;
            }
            QFrame#navFrame {
                background: white;
                border-right: 1px solid #E8E8E8;
            }
            QFrame#card {
                background: white;
                border-radius: 8px;
            }
        """)


def main():
    # Windows 任务栏图标支持 (需在创建窗口前设置)
    if os.name == "nt":
        try:
            import ctypes
            # 声明参数类型为宽字符串指针, 避免 64 位下指针截断导致设置失败
            ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID.restype = ctypes.c_long
            ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID.argtypes = [ctypes.c_wchar_p]
            ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID("SerialDebugTool.WorkAssistant")
        except Exception:
            pass
    app = QApplication(sys.argv)
    ex = SerialDebugTool()
    ex.show()
    sys.exit(app.exec())


if __name__ == '__main__':
    main()

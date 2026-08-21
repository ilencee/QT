import sys
import warnings
import os

from typing import Optional
# 支持从项目根目录独立运行本脚本
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QPushButton, QFrame, QSplitter, QTextEdit, QMessageBox, QFileDialog, QMenuBar, QMenu
)
from PyQt6.QtCore import Qt, QPoint
from PyQt6.QtGui import QFont, QCursor
from PyQt6.QtWidgets import QToolTip
from app.core.style_manager import StyleManager

class Example(QMainWindow):

    def __init__(self):
        super().__init__()
        self.dragging = False  # 标记是否正在拖动
        self.drag_position = QPoint()  # 记录拖动起始位置
        self.menubar: Optional[QMenuBar] = None
        self.file_menu: Optional[QMenu] = None
        self.initUI()

    def initUI(self):
        QToolTip.setFont(QFont('SansSerif', 10))
        self.setToolTip('This is a <b>QWidget</b> widget')

#################界面布局################
        # 创建中央widget和主布局
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        
        main_layout = QVBoxLayout(central_widget)
        
        # ===== 上区域（包含菜单栏）=====
        top_frame = QFrame()
        StyleManager.frame_glass(top_frame)  # 应用玻璃效果框架样式
        top_frame.setFixedHeight(100)
        top_layout = QHBoxLayout(top_frame)
        
        # 创建菜单栏并添加到顶部区域
        self.menubar = self.menuBar()
        if self.menubar is not None:
            StyleManager.menu_bar_style(self.menubar)
            
            self.file_menu = self.menubar.addMenu('文件')
            if self.file_menu is not None:
                self.file_menu.addAction('新建')
                open_action = self.file_menu.addAction('打开')
                #open_action.setShortcut('Ctrl+O')
                if open_action is not None:
                    open_action.triggered.connect(self.open_file)
                self.file_menu.addAction('保存')
                self.file_menu.addSeparator()
                self.file_menu.addAction('退出')
            
            # 将菜单栏添加到布局
            top_layout.addWidget(self.menubar)
        top_layout.addStretch()
        
        #top_label = QLabel("这是上方区域")
        #StyleManager.label_title(top_label)  # 应用标题样式
        #top_layout.addWidget(top_label)
        
        # 添加弹簧，让关闭按钮靠右
        top_layout.addStretch()
        
        # 添加窗口控制按钮组
        btn_style = """
            QPushButton {
                background-color: rgba(200, 200, 200, 150);
                border: none;
                border-radius: 15px;
                color: white;
                font-size: 14px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: rgba(180, 180, 180, 200);
            }
            QPushButton:pressed {
                background-color: rgba(150, 150, 150, 220);
            }
        """
        
        close_btn_style = """
            QPushButton {
                background-color: rgba(255, 100, 100, 150);
                border: none;
                border-radius: 15px;
                color: white;
                font-size: 16px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: rgba(255, 50, 50, 200);
            }
            QPushButton:pressed {
                background-color: rgba(255, 0, 0, 220);
            }
        """
        
        # 最小化按钮
        min_btn = QPushButton("−")
        min_btn.setFixedSize(30, 30)
        min_btn.setStyleSheet(btn_style)
        min_btn.clicked.connect(self.showMinimized)
        top_layout.addWidget(min_btn)
        
        # 最大化/还原按钮
        self.max_btn = QPushButton("□")
        self.max_btn.setFixedSize(30, 30)
        self.max_btn.setStyleSheet(btn_style)
        self.max_btn.clicked.connect(self.toggle_maximize)
        top_layout.addWidget(self.max_btn)
        
        # 关闭按钮
        close_btn = QPushButton("✕")
        close_btn.setFixedSize(30, 30)
        close_btn.setStyleSheet(close_btn_style)
        close_btn.clicked.connect(lambda: self.close())  # type: ignore
        top_layout.addWidget(close_btn)
        
        main_layout.addWidget(top_frame)
        
        # 为顶部区域添加鼠标事件，实现窗口拖动
        top_frame.mousePressEvent = self.top_mouse_press_event
        top_frame.mouseMoveEvent = self.top_mouse_move_event
        top_frame.mouseReleaseEvent = self.top_mouse_release_event

        # ===== 中间区域（再分左右）=====
        middle_splitter = QSplitter(Qt.Orientation.Horizontal)
        
        # 左边的区域
        left_frame = QFrame()
        StyleManager.frame_card(left_frame)  # 应用卡片式框架
        left_layout = QVBoxLayout(left_frame)
        left_layout.addWidget(QLabel("左边区域"))
        
        self.button1 = QPushButton("按钮1")
        StyleManager.button_ios_liquid_glass(self.button1)  # 应用iOS液态玻璃样式
        left_layout.addWidget(self.button1)
        
        self.button2 = QPushButton("按钮2")
        left_layout.addWidget(self.button2)
        right_frame = QFrame()
        right_layout = QVBoxLayout(right_frame)
        right_layout.addWidget(QLabel("右边区域"))
        self.text_edit = QTextEdit("这里是文本编辑区")
        self.text_edit.setReadOnly(True)  # 设置为只读，只能查看不能编辑
        StyleManager.textedit_rounded(self.text_edit)
        right_layout.addWidget(self.text_edit)
        
        middle_splitter.addWidget(left_frame)
        middle_splitter.addWidget(right_frame)
        middle_splitter.setSizes([150, 150])
        main_layout.addWidget(middle_splitter, 1)
        
        # ===== 下方区域 =====
        bottom_frame = QFrame()
        bottom_frame.setFixedHeight(80)
        bottom_layout = QHBoxLayout(bottom_frame)
        bottom_layout.addWidget(QLabel("这是下方区域"))
        main_layout.addWidget(bottom_frame)
        
        self.button = QPushButton("点击我")
        StyleManager.button_ios_liquid_glass(self.button)  # 应用iOS液态玻璃样式
        bottom_layout.addWidget(self.button)

        self.button.clicked.connect(self.show_message)

        # 设置窗口属性 - 实现双层圆角效果
        self.setGeometry(300, 300, 600, 500)
        self.setWindowTitle('分区示例')
        
        # 移除窗口原生边框，实现自定义圆角
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        
        # 给中央widget添加背景色和圆角（16px）
        central_widget.setStyleSheet("""
            QWidget {
                background-color: #f5f5f5;
                border-radius: 16px;
                border: 2px solid rgba(255, 255, 255, 100);
            }
        """)
        
        self.show()

#################菜单栏点击事件################
    def open_file(self):
        file_path, _ = QFileDialog.getOpenFileName(self, "打开文件", "", "所有文件 (*)")
        if file_path:
            with open(file_path, 'r') as file:
                content = file.read()
                self.text_edit.setPlainText(content)

    def show_message(self):
        QMessageBox.information(self, "提示", "按钮被点击了！")

    # 最大化/还原切换
    def toggle_maximize(self):
        if self.isMaximized():
            self.showNormal()
            self.max_btn.setText("□")  # 还原为最大化图标
        else:
            self.showMaximized()
            self.max_btn.setText("❐")  # 改为还原图标

    # 顶部区域鼠标按下 - 开始拖动
    def top_mouse_press_event(self, a0):  # type: ignore
        if a0.button() == Qt.MouseButton.LeftButton:
            self.dragging = True
            self.drag_position = a0.globalPosition().toPoint() - self.frameGeometry().topLeft()  # type: ignore
            a0.accept()

    # 顶部区域鼠标移动 - 执行拖动
    def top_mouse_move_event(self, a0):  # type: ignore
        if a0.buttons() & Qt.MouseButton.LeftButton and self.dragging:
            self.move(a0.globalPosition().toPoint() - self.drag_position)  # type: ignore
            a0.accept()

    # 顶部区域鼠标释放 - 结束拖动
    def top_mouse_release_event(self, a0):  # type: ignore
        if a0.button() == Qt.MouseButton.LeftButton:
            self.dragging = False
            a0.accept()


def main():
    app = QApplication(sys.argv)
    ex = Example()
    sys.exit(app.exec())


if __name__ == '__main__':
    main()

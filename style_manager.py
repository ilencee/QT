"""
样式管理器 - 统一管理所有UI组件的样式
可以方便地在不同窗口和模块中复用样式
"""

from PyQt6.QtWidgets import QGraphicsDropShadowEffect
from PyQt6.QtGui import QColor


class StyleManager:
    """统一样式管理器 - 管理所有UI组件的样式"""



    @staticmethod
    def menu_bar_style(menu_bar):
        """应用菜单栏样式"""
        menu_bar.setStyleSheet("""
            QMenuBar {
                background-color: rgba(255, 255, 255, 80);
                border-bottom: 1px solid rgba(200, 200, 200, 100);
                padding: 2px 0px;
            }
            QMenuBar::item {
                background-color: transparent;
                padding: 6px 12px;
                color: #333333;
                border-radius: 4px;
            }
            QMenuBar::item:selected {
                background-color: rgba(200, 200, 200, 100);
            }
            QMenuBar::item:pressed {
                background-color: rgba(180, 180, 180, 150);
            }
            QMenu {
                background-color: white;
                border: 1px solid rgba(200, 200, 200, 150);
                border-radius: 8px;
                padding: 5px;
            }
            QMenu::item {
                padding: 8px 20px;
                border-radius: 4px;
            }
            QMenu::item:selected {
                background-color: rgba(200, 200, 200, 100);
            }
        """)
    
    # ==================== 按钮样式 ====================
    @staticmethod
    def button_ios_liquid_glass(button):
        """iOS 26风格液态玻璃按钮"""
        
        button.setStyleSheet("""
            QPushButton {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
                    stop:0 rgba(255, 255, 255, 180),
                    stop:0.4 rgba(255, 255, 255, 120),
                    stop:0.6 rgba(255, 255, 255, 90),
                    stop:1 rgba(255, 255, 255, 50));
                border: 1px solid rgba(255, 255, 255, 200);
                border-radius: 25px;
                padding: 14px 28px;
                color: #1a1a1a;
                font-size: 16px;
                font-weight: 600;
                letter-spacing: 0.5px;
            }
            QPushButton:hover {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
                    stop:0 rgba(255, 255, 255, 220),
                    stop:0.4 rgba(255, 255, 255, 170),
                    stop:0.6 rgba(255, 255, 255, 140),
                    stop:1 rgba(255, 255, 255, 100));
                border: 1px solid rgba(255, 255, 255, 240);
            }
            QPushButton:pressed {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
                    stop:0 rgba(255, 255, 255, 130),
                    stop:0.4 rgba(255, 255, 255, 90),
                    stop:0.6 rgba(255, 255, 255, 60),
                    stop:1 rgba(255, 255, 255, 30));
                border: 1px solid rgba(255, 255, 255, 160);
            }
        """)
        
        shadow = QGraphicsDropShadowEffect()
        shadow.setBlurRadius(20)
        shadow.setXOffset(0)
        shadow.setYOffset(4)
        shadow.setColor(QColor(0, 0, 0, 40))
        button.setGraphicsEffect(shadow)
    
    @staticmethod
    def button_modern_flat(button):
        """现代扁平化按钮"""
        button.setStyleSheet("""
            QPushButton {
                background-color: #3498db;
                border: none;
                border-radius: 8px;
                padding: 12px 24px;
                color: white;
                font-size: 14px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #2980b9;
            }
            QPushButton:pressed {
                background-color: #21618c;
            }
        """)
    
    @staticmethod
    def button_minimal_outline(button):
        """极简线框按钮"""
        button.setStyleSheet("""
            QPushButton {
                background-color: transparent;
                border: 2px solid #3498db;
                border-radius: 6px;
                padding: 10px 20px;
                color: #3498db;
                font-size: 14px;
            }
            QPushButton:hover {
                background-color: rgba(52, 152, 219, 0.1);
            }
            QPushButton:pressed {
                background-color: rgba(52, 152, 219, 0.2);
            }
        """)

    @staticmethod
    def textedit_rounded(text_edit):
        """应用圆角文本编辑框样式"""
        text_edit.setStyleSheet("""
            QTextEdit {
                border: 2px solid #cccccc;
                border-radius: 10px;
                padding: 10px;
                background-color: #ffffff;
                font-size: 14px;
            }
            QTextEdit:focus {
                border: 2px solid #4CAF50;
            }
        """)
    
    # ==================== 窗口样式 ====================
    @staticmethod
    def window_rounded(window, radius=15):
        """圆角窗口"""
        window.setStyleSheet(f"""
            QMainWindow {{
                background-color: #f5f5f5;
                border-radius: {radius}px;
            }}
        """)
    
    @staticmethod
    def window_dark_mode(window):
        """深色模式窗口"""
        window.setStyleSheet("""
            QMainWindow {
                background-color: #1e1e1e;
                color: #ffffff;
            }
        """)
    
    @staticmethod
    def window_light_mode(window):
        """浅色模式窗口"""
        window.setStyleSheet("""
            QMainWindow {
                background-color: #ffffff;
                color: #333333;
            }
        """)
    
    # ==================== 框架样式 ====================
    @staticmethod
    def frame_card(frame, shadow=True):
        """卡片式框架"""
        frame.setStyleSheet("""
            QFrame {
                background-color: white;
                border-radius: 12px;
                border: 1px solid #e0e0e0;
            }
        """)
        
        if shadow:
            effect = QGraphicsDropShadowEffect()
            effect.setBlurRadius(15)
            effect.setXOffset(0)
            effect.setYOffset(2)
            effect.setColor(QColor(0, 0, 0, 30))
            frame.setGraphicsEffect(effect)
    
    @staticmethod
    def frame_glass(frame):
        """玻璃效果框架"""
        frame.setStyleSheet("""
            QFrame {
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                    stop:0 rgba(255, 255, 255, 150),
                    stop:1 rgba(255, 255, 255, 80));
                border: 1px solid rgba(255, 255, 255, 180);
                border-radius: 10px;
            }
        """)
    
    # ==================== 标签样式 ====================
    @staticmethod
    def label_title(label):
        """标题标签"""
        label.setStyleSheet("""
            QLabel {
                color: #2c3e50;
                font-size: 18px;
                font-weight: bold;
            }
        """)
    
    @staticmethod
    def label_subtitle(label):
        """副标题标签"""
        label.setStyleSheet("""
            QLabel {
                color: #7f8c8d;
                font-size: 14px;
            }
        """)
    
    # ==================== 输入框样式 ====================
    @staticmethod
    def input_modern(line_edit):
        """现代输入框"""
        line_edit.setStyleSheet("""
            QLineEdit {
                background-color: white;
                border: 2px solid #e0e0e0;
                border-radius: 8px;
                padding: 10px 15px;
                font-size: 14px;
                color: #333;
            }
            QLineEdit:focus {
                border: 2px solid #3498db;
            }
            QLineEdit:hover {
                border: 2px solid #bdc3c7;
            }
        """)
    
    # ==================== 文本编辑框样式 ====================
    @staticmethod
    def textedit_clean(text_edit):
        """简洁文本编辑框"""
        text_edit.setStyleSheet("""
            QTextEdit {
                background-color: white;
                border: 1px solid #e0e0e0;
                border-radius: 8px;
                padding: 10px;
                font-size: 13px;
                color: #333;
            }
            QTextEdit:focus {
                border: 1px solid #3498db;
            }
        """)
    
    # ==================== 首页卡片样式 ====================
    @staticmethod
    def card_info(card, color="#409EFF"):
        """信息卡片样式"""
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
    
    @staticmethod
    def scroll_area_clean(scroll):
        """简洁滚动区域样式"""
        scroll.setStyleSheet("QScrollArea { background: transparent; border: none; }")


# 为了兼容旧代码,保留别名
ButtonStyle = StyleManager

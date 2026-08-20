from PyQt6.QtWidgets import QWidget, QVBoxLayout, QScrollArea, QGridLayout, QFrame, QLabel, QHBoxLayout
from PyQt6.QtGui import QFont
from style_manager import StyleManager


class HomePage(QWidget):
    def __init__(self):
        super().__init__()
        self.initUI()
    
    def initUI(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        
        # 可滚动区域
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        StyleManager.scroll_area_clean(scroll)
        
        scroll_content = QWidget()
        scroll_layout = QVBoxLayout(scroll_content)
        scroll_layout.setSpacing(20)
        
        # 卡片网格布局 (2列)
        cards_layout = QGridLayout()
        cards_layout.setSpacing(20)
        
        # 创建卡片
        card1 = self.create_card("串口状态", "未连接", "🔌", "#409EFF")
        card2 = self.create_card("发送数据", "0 字节", "📤", "#67C23A")
        card3 = self.create_card("接收数据", "0 字节", "📥", "#E6A23C")
        card4 = self.create_card("连接时长", "00:00:00", "⏱️", "#F56C6C")
        
        cards_layout.addWidget(card1, 0, 0)
        cards_layout.addWidget(card2, 0, 1)
        cards_layout.addWidget(card3, 1, 0)
        cards_layout.addWidget(card4, 1, 1)
        
        scroll_layout.addLayout(cards_layout)
        scroll_layout.addStretch()
        
        scroll.setWidget(scroll_content)
        layout.addWidget(scroll)
    
    def create_card(self, title, value, icon, color):
        """创建信息卡片"""
        card = QFrame()
        StyleManager.card_info(card, color)
        
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

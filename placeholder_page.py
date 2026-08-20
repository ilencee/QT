from PyQt6.QtWidgets import QWidget, QVBoxLayout, QLabel
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QFont


class PlaceholderPage(QWidget):
    def __init__(self, title, icon):
        super().__init__()
        self.title = title
        self.icon = icon
        self.initUI()
    
    def initUI(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        
        # 图标和标题
        icon_label = QLabel(self.icon)
        icon_label.setFont(QFont("Microsoft YaHei", 48))
        icon_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        icon_label.setStyleSheet("color: #409EFF; padding: 20px;")
        layout.addWidget(icon_label)
        
        # 页面标题
        title_label = QLabel(self.title)
        title_label.setFont(QFont("Microsoft YaHei", 24, QFont.Weight.Bold))
        title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title_label.setStyleSheet("color: #333; padding: 10px;")
        layout.addWidget(title_label)
        
        # 提示文字
        hint_label = QLabel("此功能正在开发中...")
        hint_label.setFont(QFont("Microsoft YaHei", 14))
        hint_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        hint_label.setStyleSheet("color: #999; padding: 10px;")
        layout.addWidget(hint_label)
        
        layout.addStretch()

from PyQt6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QFrame, QLabel, QTextEdit, QPushButton
from PyQt6.QtGui import QFont


class SerialDebugPage(QWidget):
    def __init__(self):
        super().__init__()
        self.initUI()
    
    def initUI(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        
        # 串口配置区域
        config_frame = QFrame()
        config_frame.setObjectName("card")
        config_layout = QHBoxLayout(config_frame)
        config_layout.setContentsMargins(20, 20, 20, 20)
        
        # 串口选择
        port_label = QLabel("串口:")
        port_label.setFont(QFont("Microsoft YaHei", 11))
        config_layout.addWidget(port_label)
        
        # 波特率选择
        baud_label = QLabel("波特率:")
        baud_label.setFont(QFont("Microsoft YaHei", 11))
        config_layout.addWidget(baud_label)
        
        config_layout.addStretch()
        
        # 连接/断开按钮
        connect_btn = QPushButton("连接")
        connect_btn.setMinimumWidth(100)
        connect_btn.setStyleSheet("""
            QPushButton {
                background: #409EFF;
                color: white;
                border: none;
                border-radius: 6px;
                padding: 8px 16px;
                font-size: 12px;
            }
            QPushButton:hover {
                background: #66B1FF;
            }
        """)
        config_layout.addWidget(connect_btn)
        
        layout.addWidget(config_frame)
        
        # 数据显示区域
        data_frame = QFrame()
        data_frame.setObjectName("card")
        data_layout = QVBoxLayout(data_frame)
        data_layout.setContentsMargins(20, 20, 20, 20)
        
        data_title = QLabel("数据收发")
        data_title.setFont(QFont("Microsoft YaHei", 14, QFont.Weight.Bold))
        data_layout.addWidget(data_title)
        
        self.serial_text = QTextEdit()
        self.serial_text.setPlaceholderText("串口数据将在这里显示...")
        self.serial_text.setStyleSheet("""
            QTextEdit {
                background: #FAFAFA;
                border: 1px solid #E8E8E8;
                border-radius: 6px;
                padding: 10px;
                font-family: Consolas;
                font-size: 12px;
            }
        """)
        data_layout.addWidget(self.serial_text)
        
        layout.addWidget(data_frame, 1)

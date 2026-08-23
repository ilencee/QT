from PyQt6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QFrame, QLabel, 
                             QComboBox, QPushButton, QCheckBox)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QFont


class ResistorColorCodePage(QWidget):
    def __init__(self):
        super().__init__()
        self.initUI()
    
    def initUI(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(20)
        
        # 标题
        title_label = QLabel("🎨 电阻色环查询表")
        title_label.setFont(QFont("Microsoft YaHei", 18, QFont.Weight.Bold))
        title_label.setStyleSheet("color: #333; padding: 10px;")
        layout.addWidget(title_label)
        
        # 创建色环表格
        table_widget = QFrame()
        table_widget.setObjectName("card")
        table_layout = QHBoxLayout(table_widget)
        table_layout.setContentsMargins(20, 20, 20, 20)
        table_layout.setSpacing(10)
        
        # 定义色环数据
        color_data = [
            ("Black", 0, "#000000", "white"),
            ("Brown", 1, "#8B4513", "white"),
            ("Red", 2, "#FF0000", "white"),
            ("Orange", 3, "#FFA500", "black"),
            ("Yellow", 4, "#FFFF00", "black"),
            ("Green", 5, "#00FF00", "black"),
            ("Blue", 6, "#0000FF", "white"),
            ("Violet", 7, "#8B00FF", "white"),
            ("Gray", 8, "#808080", "white"),
            ("White", 9, "#FFFFFF", "black"),
            ("Gold", -1, "#FFD700", "black"),
            ("Silver", -2, "#C0C0C0", "black")
        ]
        
        # 第一环列
        band1_widget = self.create_band_column("第一环", color_data, True)
        table_layout.addWidget(band1_widget)
        
        # 第二环列
        band2_widget = self.create_band_column("第二环", color_data, True)
        table_layout.addWidget(band2_widget)
        
        # 第三环列
        band3_widget = self.create_band_column("第三环", color_data, True)
        table_layout.addWidget(band3_widget)
        
        # 第四环列
        band4_widget = self.create_band_column("第四环", color_data, True)
        table_layout.addWidget(band4_widget)
        
        # 乘数列
        multiplier_data = [
            ("x 1", "#000000", "white"),
            ("x 10", "#8B4513", "white"),
            ("x 100", "#FF0000", "white"),
            ("x 1k", "#FFA500", "black"),
            ("x 10k", "#FFFF00", "black"),
            ("x 100k", "#00FF00", "black"),
            ("x 1M", "#0000FF", "white"),
            ("x 10M", "#8B00FF", "white"),
            ("x 100M", "#808080", "white"),
            ("x 1G", "#FFFFFF", "black"),
            ("x 0.1", "#FFD700", "black"),
            ("x 0.01", "#C0C0C0", "black")
        ]
        multiplier_widget = self.create_multiplier_column("乘数", multiplier_data)
        table_layout.addWidget(multiplier_widget)
        
        # 精度列
        tolerance_data = [
            ("± 1%", "#8B4513", "white"),
            ("± 2%", "#FF0000", "white"),
            ("", "#FFA500", "black"),
            ("", "#FFFF00", "black"),
            ("± 0.5%", "#00FF00", "black"),
            ("± 0.25%", "#0000FF", "white"),
            ("± 0.10%", "#8B00FF", "white"),
            ("± 0.05%", "#808080", "white"),
            ("", "#FFFFFF", "black"),
            ("", "#FFFFFF", "black"),
            ("± 5%", "#FFD700", "black"),
            ("± 10%", "#C0C0C0", "black")
        ]
        tolerance_widget = self.create_tolerance_column("精度容差", tolerance_data)
        table_layout.addWidget(tolerance_widget)
        
        layout.addWidget(table_widget)
        
        # 查询区域
        query_frame = QFrame()
        query_frame.setObjectName("card")
        query_layout = QVBoxLayout(query_frame)
        query_layout.setContentsMargins(20, 20, 20, 20)
        
        query_title = QLabel("🔍 快速查询")
        query_title.setFont(QFont("Microsoft YaHei", 14, QFont.Weight.Bold))
        query_layout.addWidget(query_title)
        
        # 色环选择器
        selector_layout = QHBoxLayout()
        
        self.band1_combo = self.create_color_combo("第一环:")
        selector_layout.addWidget(self.band1_combo)
        
        self.band2_combo = self.create_color_combo("第二环:")
        selector_layout.addWidget(self.band2_combo)
        
        self.band3_combo = self.create_color_combo("第三环:")
        selector_layout.addWidget(self.band3_combo)
        
        self.multiplier_combo = self.create_multiplier_combo("乘数:")
        selector_layout.addWidget(self.multiplier_combo)
        
        self.tolerance_combo = self.create_tolerance_combo("精度:")
        selector_layout.addWidget(self.tolerance_combo)

        # 五环电阻开关: 勾选后第三环参与计算 (四环默认忽略第三环)
        self.five_band_check = QCheckBox("五环电阻")
        self.five_band_check.setFont(QFont("Microsoft YaHei", 10))
        self.five_band_check.setCursor(Qt.CursorShape.PointingHandCursor)
        self.five_band_check.toggled.connect(self.calculate_resistance)
        selector_layout.addWidget(self.five_band_check)
        
        query_layout.addLayout(selector_layout)
        
        # 结果显示
        result_layout = QHBoxLayout()
        result_label = QLabel("电阻值:")
        result_label.setFont(QFont("Microsoft YaHei", 12))
        result_layout.addWidget(result_label)
        
        self.result_value = QLabel("请选择色环")
        self.result_value.setFont(QFont("Microsoft YaHei", 16, QFont.Weight.Bold))
        self.result_value.setStyleSheet("color: #409EFF; padding: 10px;")
        result_layout.addWidget(self.result_value)
        result_layout.addStretch()
        
        query_layout.addLayout(result_layout)
        
        # 计算按钮
        calc_btn = QPushButton("计算电阻值")
        calc_btn.setMinimumHeight(40)
        calc_btn.setFont(QFont("Microsoft YaHei", 12))
        calc_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        calc_btn.setStyleSheet("""
            QPushButton {
                background: #409EFF;
                color: white;
                border: none;
                border-radius: 6px;
                padding: 8px 20px;
            }
            QPushButton:hover {
                background: #66B1FF;
            }
            QPushButton:pressed {
                background: #3A8EE6;
            }
        """)
        calc_btn.clicked.connect(self.calculate_resistance)
        query_layout.addWidget(calc_btn)
        
        layout.addWidget(query_frame)
        layout.addStretch()
    
    def create_band_column(self, title, color_data, show_value):
        """创建色环列"""
        column = QFrame()
        column.setStyleSheet("background: white; border-radius: 6px;")
        layout = QVBoxLayout(column)
        layout.setContentsMargins(5, 5, 5, 5)
        layout.setSpacing(3)
        
        # 标题
        title_label = QLabel(title)
        title_label.setFont(QFont("Microsoft YaHei", 10, QFont.Weight.Bold))
        title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title_label.setStyleSheet("color: #333; padding: 5px;")
        layout.addWidget(title_label)
        
        # 色环颜色
        for name, value, bg_color, text_color in color_data:
            if value >= 0 or show_value:
                cell = QLabel(f"{name} {value if value >= 0 else ''}")
                cell.setFont(QFont("Microsoft YaHei", 9))
                cell.setAlignment(Qt.AlignmentFlag.AlignCenter)
                cell.setMinimumHeight(25)
                cell.setStyleSheet(f"""
                    QLabel {{
                        background: {bg_color};
                        color: {text_color};
                        border: 1px solid #ddd;
                        border-radius: 3px;
                        padding: 3px;
                    }}
                """)
                layout.addWidget(cell)
        
        return column
    
    def create_multiplier_column(self, title, multiplier_data):
        """创建乘数列"""
        column = QFrame()
        column.setStyleSheet("background: white; border-radius: 6px;")
        layout = QVBoxLayout(column)
        layout.setContentsMargins(5, 5, 5, 5)
        layout.setSpacing(3)
        
        # 标题
        title_label = QLabel(title)
        title_label.setFont(QFont("Microsoft YaHei", 10, QFont.Weight.Bold))
        title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title_label.setStyleSheet("color: #333; padding: 5px;")
        layout.addWidget(title_label)
        
        # 乘数值
        for text, bg_color, text_color in multiplier_data:
            cell = QLabel(text)
            cell.setFont(QFont("Microsoft YaHei", 9))
            cell.setAlignment(Qt.AlignmentFlag.AlignCenter)
            cell.setMinimumHeight(25)
            cell.setStyleSheet(f"""
                QLabel {{
                    background: {bg_color};
                    color: {text_color};
                    border: 1px solid #ddd;
                    border-radius: 3px;
                    padding: 3px;
                }}
            """)
            layout.addWidget(cell)
        
        return column
    
    def create_tolerance_column(self, title, tolerance_data):
        """创建精度列"""
        column = QFrame()
        column.setStyleSheet("background: white; border-radius: 6px;")
        layout = QVBoxLayout(column)
        layout.setContentsMargins(5, 5, 5, 5)
        layout.setSpacing(3)
        
        # 标题
        title_label = QLabel(title)
        title_label.setFont(QFont("Microsoft YaHei", 10, QFont.Weight.Bold))
        title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title_label.setStyleSheet("color: #333; padding: 5px;")
        layout.addWidget(title_label)
        
        # 精度值
        for text, bg_color, text_color in tolerance_data:
            cell = QLabel(text)
            cell.setFont(QFont("Microsoft YaHei", 9))
            cell.setAlignment(Qt.AlignmentFlag.AlignCenter)
            cell.setMinimumHeight(25)
            cell.setStyleSheet(f"""
                QLabel {{
                    background: {bg_color};
                    color: {text_color};
                    border: 1px solid #ddd;
                    border-radius: 3px;
                    padding: 3px;
                }}
            """)
            layout.addWidget(cell)
        
        return column
    
    def create_color_combo(self, label_text):
        """创建色环下拉框, 容器上挂 combo 引用供计算直接使用"""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(0, 0, 0, 0)
        
        label = QLabel(label_text)
        label.setFont(QFont("Microsoft YaHei", 10))
        layout.addWidget(label)
        
        combo = QComboBox()
        combo.setFont(QFont("Microsoft YaHei", 10))
        combo.setMinimumHeight(35)
        combo.addItems(["Black (0)", "Brown (1)", "Red (2)", "Orange (3)", "Yellow (4)",
                       "Green (5)", "Blue (6)", "Violet (7)", "Gray (8)", "White (9)"])
        layout.addWidget(combo)
        widget.combo = combo  # type: ignore[attr-defined]
        
        return widget
    
    def create_multiplier_combo(self, label_text):
        """创建乘数下拉框, 容器上挂 combo 引用"""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(0, 0, 0, 0)
        
        label = QLabel(label_text)
        label.setFont(QFont("Microsoft YaHei", 10))
        layout.addWidget(label)
        
        combo = QComboBox()
        combo.setFont(QFont("Microsoft YaHei", 10))
        combo.setMinimumHeight(35)
        combo.addItems(["x 1", "x 10", "x 100", "x 1k", "x 10k", "x 100k", 
                       "x 1M", "x 10M", "x 100M", "x 1G", "x 0.1", "x 0.01"])
        layout.addWidget(combo)
        widget.combo = combo  # type: ignore[attr-defined]
        
        return widget
    
    def create_tolerance_combo(self, label_text):
        """创建精度下拉框, 容器上挂 combo 引用"""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(0, 0, 0, 0)
        
        label = QLabel(label_text)
        label.setFont(QFont("Microsoft YaHei", 10))
        layout.addWidget(label)
        
        combo = QComboBox()
        combo.setFont(QFont("Microsoft YaHei", 10))
        combo.setMinimumHeight(35)
        combo.addItems(["± 1%", "± 2%", "± 0.5%", "± 0.25%", "± 0.10%", 
                       "± 0.05%", "± 5%", "± 10%"])
        layout.addWidget(combo)
        widget.combo = combo  # type: ignore[attr-defined]
        
        return widget
    
    def calculate_resistance(self):
        """计算电阻值"""
        # 获取选择的索引 (直接引用已挂载的 combo, 替代脆弱的 findChild)
        band1_index = self.band1_combo.combo.currentIndex()  # type: ignore[attr-defined]
        band2_index = self.band2_combo.combo.currentIndex()  # type: ignore[attr-defined]
        band3_index = self.band3_combo.combo.currentIndex()  # type: ignore[attr-defined]
        multiplier_index = self.multiplier_combo.combo.currentIndex()  # type: ignore[attr-defined]
        tolerance_index = self.tolerance_combo.combo.currentIndex()  # type: ignore[attr-defined]
        
        # 映射值
        band1_values = [0, 1, 2, 3, 4, 5, 6, 7, 8, 9]
        multiplier_values = [1, 10, 100, 1000, 10000, 100000, 1000000, 
                           10000000, 100000000, 1000000000, 0.1, 0.01]
        tolerance_values = [1, 2, 0.5, 0.25, 0.10, 0.05, 5, 10]
        
        band1 = band1_values[band1_index]
        band2 = band1_values[band2_index]
        multiplier = multiplier_values[multiplier_index]
        tolerance = tolerance_values[tolerance_index]
        
        # 计算电阻值: 四环 = 2 数字环 + 乘数; 五环 = 3 数字环 + 乘数
        if self.five_band_check.isChecked():
            band3 = band1_values[band3_index]
            resistance = (band1 * 100 + band2 * 10 + band3) * multiplier
        else:
            resistance = (band1 * 10 + band2) * multiplier
        
        # 格式化显示
        if resistance >= 1000000000:
            result = f"{resistance / 1000000000:.2f} GΩ"
        elif resistance >= 1000000:
            result = f"{resistance / 1000000:.2f} MΩ"
        elif resistance >= 1000:
            result = f"{resistance / 1000:.2f} kΩ"
        else:
            result = f"{resistance:.2f} Ω"
        
        result += f" ±{tolerance}%"
        
        self.result_value.setText(result)

"""
功率变换计算工具页面

功能:
1. LDO 线性稳压器(如 78L05)降压电路计算
2. 串联限流/分压电阻计算
3. LDO 功耗与温升/结温计算
4. 电阻选型与散热建议

电路原理:
    输入 Vin → [串联电阻 R] → 78L05 → 输出 Vout
    稳压器维持最小压降 Vdrop 正常工作, 多余的压降由串联电阻承担,
    从而降低稳压器本身的功耗与温升。
"""

import math
from pathlib import Path

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QFrame, QLabel,
    QComboBox, QPushButton, QLineEdit, QFormLayout, QGridLayout,
    QSizePolicy, QCheckBox,
)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QFont, QDoubleValidator

from app.core.config_manager import ConfigManager, app_root
from app.core.deepseek_client import DeepSeekThread, DeepSeekDialog, load_api_config


class PowerConversionPage(QWidget):
    """功率变换计算工具页面"""

    # 出厂默认型号库 (config.json 中 power_conversion.regulators 可覆盖/编辑)
    # 常用 LDO 稳压器参数库 (输出电压V, 最小压降V, 热阻RθJA °C/W, 最大电流mA, 静态电流mA)
    # 贴片封装优先, 直插型号放在后面作为参考
    # 注意: 78Lxx 系列贴片封装为 SOT-89 (无 SOT-223)
    DEFAULT_REGULATORS = {
        # ===== 贴片 LDO (优先推荐) =====
        "78L05 (SOT-89, 100mA)":          {"vout": 5.0,  "vdrop": 2.0, "rthja": 140, "imax": 100,  "iq": 6},
        "78L08 (SOT-89, 100mA)":          {"vout": 8.0,  "vdrop": 1.7, "rthja": 140, "imax": 100,  "iq": 6},
        "AMS1117-3.3 (SOT-223, 1A)":      {"vout": 3.3,  "vdrop": 1.2, "rthja": 90,  "imax": 1000, "iq": 5},
        "AMS1117-5.0 (SOT-223, 1A)":      {"vout": 5.0,  "vdrop": 1.2, "rthja": 90,  "imax": 1000, "iq": 5},
        "HT7533 (SOT-89, 100mA)":         {"vout": 3.3,  "vdrop": 0.5, "rthja": 140, "imax": 100,  "iq": 0.005},
        "HT7550 (SOT-89, 100mA)":         {"vout": 5.0,  "vdrop": 0.5, "rthja": 140, "imax": 100,  "iq": 0.005},
        "XC6206P332MR (SOT-23, 200mA)":   {"vout": 3.3,  "vdrop": 0.3, "rthja": 250, "imax": 200,  "iq": 0.002},
        "ME6211C33 (SOT-23-5, 500mA)":    {"vout": 3.3,  "vdrop": 0.25, "rthja": 200, "imax": 500,  "iq": 0.05},
        "LP5907MFX-3.3 (SOT-23-5, 250mA)": {"vout": 3.3, "vdrop": 0.1, "rthja": 220, "imax": 250,  "iq": 0.015},
        "RT9013-33PB (SOT-23-5, 500mA)":  {"vout": 3.3,  "vdrop": 0.15, "rthja": 200, "imax": 500,  "iq": 0.05},
        "MIC5205-3.3 (SOT-23-5, 150mA)":  {"vout": 3.3,  "vdrop": 0.2, "rthja": 220, "imax": 150,  "iq": 0.11},
        # ===== 直插 LDO (参考) =====
        "78L05 (TO-92, 100mA)":           {"vout": 5.0,  "vdrop": 2.0, "rthja": 200, "imax": 100,  "iq": 6},
        "78L33 (TO-92, 100mA)":           {"vout": 3.3,  "vdrop": 1.7, "rthja": 200, "imax": 100,  "iq": 6},
        "7805 (TO-220, 1A)":              {"vout": 5.0,  "vdrop": 2.0, "rthja": 65,  "imax": 1000, "iq": 8},
        "7808 (TO-220, 1A)":              {"vout": 8.0,  "vdrop": 2.0, "rthja": 65,  "imax": 1000, "iq": 8},
        "7812 (TO-220, 1A)":              {"vout": 12.0, "vdrop": 2.0, "rthja": 65,  "imax": 1000, "iq": 8},
        # ===== 自定义 =====
        "自定义":                          {"vout": 5.0,  "vdrop": 2.0, "rthja": 200, "imax": 100,  "iq": 5},
    }

    # E24 标准电阻系列 (乘数)
    E24 = [1.0, 1.1, 1.2, 1.3, 1.5, 1.6, 1.8, 2.0, 2.2, 2.4, 2.7,
           3.0, 3.3, 3.6, 3.9, 4.3, 4.7, 5.1, 5.6, 6.2, 6.8, 7.5,
           8.2, 9.1]

    # 标准功率等级 (W)
    POWER_RATINGS = [0.125, 0.25, 0.5, 1, 2, 3, 5]

    # 电阻封装参数: 额定功率W / 相对单价 / 相对PCB占用面积 (用于选型对比)
    # 价格与面积为相对值 (以 0603 为基准 1.0), 用于方案间对比, 非绝对报价
    PACKAGES = {
        "0603":        {"w": 0.1,   "price": 1.0, "area": 1.0},
        "0805":        {"w": 0.125, "price": 1.3, "area": 1.8},
        "1206":        {"w": 0.25,  "price": 1.6, "area": 3.2},
        "2512":        {"w": 1.0,   "price": 4.5, "area": 7.5},
        "大功率贴片":   {"w": 2.0,   "price": 12,  "area": 16},
        "插件绕线电阻": {"w": 5.0,   "price": 6.0, "area": 22},
    }
    # 可并联替代的小封装 (按性价比/空间权衡排序)
    PARALLEL_PACKAGES = ("1206", "0805", "0603")

    def __init__(self):
        super().__init__()
        # 配置文件统一管理默认参数 / API / 型号库 (方便手动修改)
        self.cfg = ConfigManager(str(app_root() / "config.json"))
        # 确保 config.json 存在: 首次运行自动生成完整模板, 后续可直接手动编辑
        if "power_conversion" not in self.cfg.config:
            self.cfg.config["power_conversion"] = self.cfg.get_factory_defaults()["power_conversion"]
        self.cfg.save_config()
        # 型号库: 优先使用 config.json, 缺失时回退到代码内置
        self.REGULATORS = (
            self.cfg.config.get("power_conversion", {}).get("regulators")
            or dict(self.DEFAULT_REGULATORS)
        )
        self.initUI()

    def initUI(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(20)

        # 全局控件样式: 统一输入框/下拉框/复选框 (Element 风格)
        self.setStyleSheet("""
            QLineEdit {
                background: #FFFFFF; border: 1px solid #DCDFE6;
                border-radius: 6px; padding: 4px 10px;
                font-family: "Microsoft YaHei"; font-size: 10pt; color: #303133;
            }
            QLineEdit:hover { border-color: #C0C4CC; }
            QLineEdit:focus { border: 1px solid #409EFF; }
            QComboBox {
                background: #FFFFFF; border: 1px solid #DCDFE6;
                border-radius: 6px; padding: 4px 10px;
                font-family: "Microsoft YaHei"; font-size: 10pt; color: #303133;
            }
            QComboBox:hover { border-color: #C0C4CC; }
            QComboBox:focus { border: 1px solid #409EFF; }
            QComboBox::drop-down { border: none; width: 26px; }
            QComboBox QAbstractItemView {
                background: #FFFFFF; border: 1px solid #DCDFE6;
                selection-background-color: #ECF5FF; selection-color: #409EFF;
                font-family: "Microsoft YaHei"; font-size: 10pt;
            }
            QCheckBox {
                font-family: "Microsoft YaHei"; font-size: 10pt; color: #303133;
            }
            QCheckBox::indicator {
                width: 16px; height: 16px; border: 1px solid #DCDFE6;
                border-radius: 4px; background: #FFFFFF;
            }
            QCheckBox::indicator:hover { border-color: #409EFF; }
            QCheckBox::indicator:checked {
                background: #409EFF; border-color: #409EFF;
            }
        """)

        # 主布局: 左侧输入, 右侧结果
        main_layout = QHBoxLayout()
        main_layout.setSpacing(20)

        main_layout.addWidget(self.create_input_card())
        main_layout.addWidget(self.create_result_card(), 1)

        layout.addLayout(main_layout)
        layout.addStretch()

        # 底部操作提示 (保存/恢复默认等, 不挤占右侧计算空间)
        self.op_msg_label = QLabel(" ")
        self.op_msg_label.setFont(QFont("Microsoft YaHei", 10))
        self.op_msg_label.setWordWrap(True)
        self.op_msg_label.setStyleSheet(
            "color: #67C23A; background: #F0F9EB; border: 1px solid #67C23A;"
            "border-radius: 6px; padding: 8px 12px;"
        )
        layout.addWidget(self.op_msg_label)

        # 初始计算 (显示默认参数结果)
        self.calculate()

        # 加载保存的默认参数 (setText 会自动触发实时计算)
        self.load_defaults()

    # ==================== 输入卡片 ====================
    def create_input_card(self):
        """创建参数输入卡片"""
        frame = QFrame()
        frame.setObjectName("card")
        frame.setFixedWidth(300)
        layout = QVBoxLayout(frame)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(12)

        layout.addWidget(self._card_title("参数输入", "⚙️"))

        # 型号选择
        model_label = QLabel("稳压器型号")
        model_label.setFont(QFont("Microsoft YaHei", 10))
        model_label.setStyleSheet("color: #606266;")
        layout.addWidget(model_label)
        self.model_combo = QComboBox()
        self.model_combo.setMinimumHeight(36)
        self.model_combo.addItems(list(self.REGULATORS.keys()))
        self.model_combo.currentIndexChanged.connect(self.on_regulator_changed)
        layout.addWidget(self.model_combo)

        # 最大电流提示 (徽章) - 已隐藏
        self.imax_label = QLabel()
        self.imax_label.setFont(QFont("Microsoft YaHei", 9))
        self.imax_label.setWordWrap(True)
        self.imax_label.setStyleSheet(
            "background: #ECF5FF; color: #409EFF; border-radius: 4px;"
            "padding: 5px 8px;"
        )
        self.imax_label.hide()
        layout.addWidget(self.imax_label)

        # 降压方式: 复选框, 默认串联电阻; 取消勾选 = LDO 全压降
        self.mode_check = QCheckBox("串联限流电阻降压")
        self.mode_check.setMinimumHeight(30)
        self.mode_check.setChecked(True)
        self.mode_check.setToolTip(
            "勾选: 串联电阻承担 Vin−Vout 超出 Vdrop 的压降, LDO 功耗小\n"
            "取消: LDO 直接承受全部压降, 功耗与温升显著增大"
        )
        self.mode_check.toggled.connect(self.calculate)
        layout.addWidget(self.mode_check)

        # 表单输入 (标签统一样式, 与右侧结果卡片视觉对齐)
        form = QFormLayout()
        form.setSpacing(10)
        form.setLabelAlignment(Qt.AlignmentFlag.AlignRight)

        # 默认值从 config.json 的 power_conversion.defaults 读取
        self.vin_edit = self.create_edit(str(self.get_default("vin", "12")))
        self._form_row(form, "输入电压 Vin (V):", self.vin_edit)

        self.vout_edit = self.create_edit("5")
        self._form_row(form, "输出电压 Vout (V):", self.vout_edit)

        self.vdrop_edit = self.create_edit("2")
        self._form_row(form, "LDO 最小压降 (V):", self.vdrop_edit)

        self.current_edit = self.create_edit(str(self.get_default("current_ma", "100")))
        self._form_row(form, "负载电流 I (mA):", self.current_edit)

        self.derate_edit = self.create_edit(str(self.get_default("derate", "80")))
        self._form_row(form, "降额系数 (%):", self.derate_edit)

        self.tamb_edit = self.create_edit(str(self.get_default("tamb", "25")))
        self._form_row(form, "环境温度 (°C):", self.tamb_edit)

        self.rthja_edit = self.create_edit(str(self.get_default("rthja", "")))
        self._form_row(form, "热阻 RθJA (°C/W):", self.rthja_edit)

        self.iq_edit = self.create_edit(str(self.get_default("iq", "")))
        self._form_row(form, "静态电流 Iq (mA):", self.iq_edit)

        layout.addLayout(form)

        # 实时计算提示
        live_label = QLabel("🔄 实时计算: 修改参数后结果自动更新")
        live_label.setFont(QFont("Microsoft YaHei", 9))
        live_label.setStyleSheet(
            "color: #67C23A; background: #F0F9EB; border-radius: 4px;"
            "padding: 6px 8px;"
        )
        layout.addWidget(live_label)

        # 保存/恢复默认参数按钮
        btn_layout = QHBoxLayout()
        btn_layout.setSpacing(10)

        save_btn = QPushButton("💾 保存为默认")
        save_btn.setMinimumHeight(36)
        save_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        save_btn.setStyleSheet("""
            QPushButton {
                background: #67C23A; color: white; border: none;
                border-radius: 6px; padding: 6px 12px;
                font-weight: bold;
            }
            QPushButton:hover { background: #85CE61; }
            QPushButton:pressed { background: #5DAF34; }
        """)
        save_btn.clicked.connect(self.save_defaults)
        btn_layout.addWidget(save_btn, 1)

        reset_btn = QPushButton("↺ 恢复默认")
        reset_btn.setMinimumHeight(36)
        reset_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        reset_btn.setStyleSheet("""
            QPushButton {
                background: #909399; color: white; border: none;
                border-radius: 6px; padding: 6px 12px;
                font-weight: bold;
            }
            QPushButton:hover { background: #A6A9AD; }
            QPushButton:pressed { background: #82848A; }
        """)
        reset_btn.clicked.connect(self.restore_factory_defaults)
        btn_layout.addWidget(reset_btn, 1)

        layout.addLayout(btn_layout)

        # AI 分析按钮 (API Key 在 config.json 的 power_conversion.api 中配置)
        ai_btn = QPushButton("🤖 AI 分析当前数据")
        ai_btn.setMinimumHeight(38)
        ai_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        ai_btn.setStyleSheet("""
            QPushButton {
                background: #409EFF; color: white; border: none;
                border-radius: 6px; padding: 6px 12px;
                font-weight: bold;
            }
            QPushButton:hover { background: #66B1FF; }
            QPushButton:pressed { background: #337ECC; }
        """)
        ai_btn.clicked.connect(self.analyze_with_ai)
        layout.addWidget(ai_btn)
        layout.addStretch()

        # 初始填充型号参数
        self.on_regulator_changed(0)

        return frame

    # ==================== 视觉辅助 ====================
    def _card_title(self, text, icon):
        """统一卡片标题: 蓝色竖条 + 图标 + 文字"""
        bar = QFrame()
        bar.setFixedSize(4, 20)
        bar.setStyleSheet("background: #409EFF; border-radius: 2px;")
        label = QLabel(f"{icon}  {text}")
        label.setFont(QFont("Microsoft YaHei", 14, QFont.Weight.Bold))
        label.setStyleSheet("color: #303133;")
        h = QHBoxLayout()
        h.setSpacing(8)
        h.addWidget(bar)
        h.addWidget(label)
        h.addStretch()
        wrap = QWidget()
        wrap.setLayout(h)
        return wrap

    def _form_row(self, form, text, widget):
        """向表单添加统一样式的行 (标签灰色, 与输入框垂直居中)"""
        label = QLabel(text)
        label.setFont(QFont("Microsoft YaHei", 10))
        label.setStyleSheet("color: #606266;")
        form.addRow(label, widget)

    def get_default(self, key, fallback=""):
        """从 config.json 读取功率变换页默认参数"""
        return self.cfg.config.get("power_conversion", {}).get("defaults", {}).get(key, fallback)

    def create_edit(self, default="0"):
        """创建带数字校验的输入框"""
        edit = QLineEdit(default)
        edit.setMinimumHeight(36)
        edit.setAlignment(Qt.AlignmentFlag.AlignRight)
        validator = QDoubleValidator(0.0, 100000.0, 4)
        validator.setNotation(QDoubleValidator.Notation.StandardNotation)
        edit.setValidator(validator)
        edit.textChanged.connect(self.calculate)  # 实时计算
        return edit

    def on_regulator_changed(self, index):
        """型号切换时自动填充参数"""
        name = self.model_combo.currentText()
        params = self.REGULATORS.get(name, self.REGULATORS["自定义"])
        is_custom = (name == "自定义")

        # 型号确定后输出电压固定, 不可修改 (仅"自定义"可编辑)
        self.vout_edit.setText(str(params["vout"]))
        self.vout_edit.setEnabled(is_custom)
        self.vout_edit.setToolTip(
            "该型号输出电压固定" if not is_custom else "自定义输出电压"
        )

        self.vdrop_edit.setText(str(params["vdrop"]))
        self.rthja_edit.setText(str(params["rthja"]))
        self.iq_edit.setText(str(params["iq"]))

    # ==================== 结果卡片 ====================
    def create_result_card(self):
        """创建结果展示卡片"""
        frame = QFrame()
        frame.setObjectName("card")
        layout = QVBoxLayout(frame)
        layout.setContentsMargins(20, 16, 20, 16)
        layout.setSpacing(10)

        layout.addWidget(self._card_title("计算结果", "📊"))

        # 电路示意
        diagram = QLabel("Vin ──▶ [R] ──▶ | LDO | ──▶ Vout")
        diagram.setFont(QFont("Consolas", 11))
        diagram.setAlignment(Qt.AlignmentFlag.AlignCenter)
        diagram.setStyleSheet(
            "color: #409EFF; background: #F0F7FF; padding: 6px;"
            "border-radius: 6px; font-weight: bold;"
        )
        layout.addWidget(diagram)

        # 结果网格 (2列等宽, 行视觉对齐)
        grid = QGridLayout()
        grid.setSpacing(10)
        grid.setColumnStretch(0, 1)
        grid.setColumnStretch(1, 1)

        self.result_r = self.create_result_cell(grid, 0, 0, "串联电阻 R (Ω)", "#409EFF")
        self.result_p_ldo = self.create_result_cell(grid, 0, 1, "LDO 功耗 (W)", "#E6A23C")
        self.result_v_r = self.create_result_cell(grid, 1, 0, "电阻压降 (V)", "#67C23A")
        self.result_delta_t = self.create_result_cell(grid, 1, 1, "温升 ΔT (°C)", "#F56C6C")
        self.result_p_r = self.create_result_cell(grid, 2, 0, "电阻功率 (W)", "#67C23A")
        self.result_tj = self.create_result_cell(grid, 2, 1, "结温 Tj (°C)", "#F56C6C")
        self.result_pin = self.create_result_cell(grid, 3, 0, "输入功率 P_in (W)", "#409EFF")
        self.result_eff = self.create_result_cell(grid, 3, 1, "效率 η (%)", "#909399")

        layout.addLayout(grid)

        # 警告信息
        self.warn_label = QLabel(" ")
        self.warn_label.setFont(QFont("Microsoft YaHei", 11))
        self.warn_label.setWordWrap(True)
        self.warn_label.setStyleSheet(
            "color: #E6A23C; background: #FDF6EC; border: 1px solid #E6A23C;"
            "border-radius: 6px; padding: 8px 10px;"
        )
        layout.addWidget(self.warn_label)

        # 公式说明
        note = QLabel(
            "计算说明\n"
            "• 串联电阻压降 V_R(V) = Vin − Vout − Vdrop\n"
            "• 电阻阻值 R(Ω) = V_R / I,  电阻功率 P_R(W) = V_R × I\n"
            "• LDO 功耗 P(W) = Vdrop×I + (Vout+Vdrop)×Iq\n"
            "• 温升 ΔT(°C) = P × RθJA,  结温 Tj(°C) = 环境温度 + ΔT"
        )
        note.setFont(QFont("Microsoft YaHei", 9))
        note.setStyleSheet(
            "color: #606266; background: #F5F7FA; border-radius: 6px;"
            "padding: 6px 10px;"
        )
        layout.addWidget(note)

        return frame

    def create_result_cell(self, grid, row, col, title, color):
        """创建结果小卡片 (富文本 QLabel, 换行自动撑高不被裁剪)"""
        label = QLabel()
        label.setWordWrap(True)
        label.setTextFormat(Qt.TextFormat.RichText)
        # 统一行高并居中, 与左侧输入行视觉对齐 (紧凑)
        label.setMinimumHeight(46)
        label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        # 垂直方向按内容高度伸展, 换行多行时自动撑高不被裁剪
        label.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Minimum)
        label.setStyleSheet("""
            QLabel {
                background: #F5F7FA;
                border-radius: 6px;
                padding: 6px 10px;
            }
        """)
        label.setProperty("cell_title", title)
        label.setProperty("cell_color", color)
        label.setText(self.cell_html(title, "—", color))
        grid.addWidget(label, row, col)
        return label

    def cell_html(self, title, value, color):
        """生成结果格子富文本 HTML (值中的换行转为 <br>)"""
        safe_value = str(value).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
        safe_value = safe_value.replace("\n", "<br>")
        return (
            f"<span style='color:#909399; font-size:9.5pt;'>{title}</span>"
            f"<br>"
            f"<span style='color:{color}; font-size:12pt; font-weight:bold;'>{safe_value}</span>"
        )

    def set_cell_value(self, label, value):
        """更新结果格子数值"""
        label.setText(self.cell_html(
            label.property("cell_title"),
            value,
            label.property("cell_color"),
        ))

    # ==================== 计算逻辑 ====================
    def calculate(self):
        """实时执行计算 (参数变化时自动调用)"""
        # 结果面板尚未创建时跳过
        if not hasattr(self, "result_r"):
            return

        try:
            vin = float(self.vin_edit.text().strip())
            vout = float(self.vout_edit.text().strip())
            vdrop = float(self.vdrop_edit.text().strip())
            current_ma = float(self.current_edit.text().strip())
            tamb = float(self.tamb_edit.text().strip())
            rthja = float(self.rthja_edit.text().strip())
            iq = float(self.iq_edit.text().strip())
            derate = float(self.derate_edit.text().strip()) / 100.0
        except ValueError:
            self.clear_result()
            self.show_warning("请输入有效的数字!", "#F56C6C")
            return

        if vin <= 0 or vout < 0 or current_ma <= 0 or rthja <= 0:
            self.clear_result()
            self.show_warning("电压、电流、热阻必须大于 0!", "#F56C6C")
            return

        if not (0 < derate <= 1):
            self.clear_result()
            self.show_warning("降额系数必须在 0% ~ 100% 之间!", "#F56C6C")
            return

        i = current_ma / 1000.0  # 转换为安培
        iq_a = iq / 1000.0  # 静态电流转换为安培
        total_drop = vin - vout  # 总压降

        if total_drop <= 0:
            self.clear_result()
            self.show_warning("输入电压必须大于输出电压!", "#F56C6C")
            return

        if total_drop < vdrop:
            self.clear_result()
            self.show_warning(
                f"输入电压过低: 总压降 {total_drop:.2f}V < 最小压降 {vdrop:.2f}V,\n"
                f"稳压器无法正常稳压, 请提高输入电压至至少 {vout + vdrop:.2f}V!",
                "#F56C6C"
            )
            return

        # 降压方式: 勾选=串联电阻, 取消=LDO 全压降
        no_resistor = not self.mode_check.isChecked()

        if no_resistor:
            # 无串联电阻: LDO 直接承受全部压降
            v_ldo = total_drop
            v_r = 0.0
            vin_ldo = vin
            r = None
        else:
            # LDO 承担最小压降, 剩余压降由串联电阻承担
            v_ldo = vdrop
            v_r = total_drop - vdrop
            vin_ldo = vout + vdrop  # LDO 输入引脚电压
            r = v_r / i

        # 电阻功率
        p_r = v_r * i
        # LDO 功耗 = 调整管损耗(压降×负载电流) + 静态电流损耗(Vin_ldo×Iq)
        p_ldo = v_ldo * i + vin_ldo * iq_a
        # 温升
        delta_t = p_ldo * rthja
        # 结温
        tj = tamb + delta_t
        # 输入功率 (含静态电流)
        p_in = vin * (i + iq_a)
        # 总损耗 = 电阻损耗 + LDO 损耗
        p_loss = p_r + p_ldo
        # 实际效率 = 输出功率 / 输入功率 (计入静态电流, 随负载/Iq/Vin 变化)
        efficiency = vout * i / p_in * 100

        # 选型建议
        if no_resistor:
            r_text = "无串联电阻\n(LDO 承担全部压降)"
        elif r is None or r <= 0:
            r_text = "无需串联电阻\n(LDO 独立承担全部压降)"
        else:
            std_r = self.nearest_e24(r)
            r_text = f"{self.format_value(r, 'Ω')}\n(E24 推荐 {self.format_value(std_r, 'Ω')})"

        if p_r > 0:
            rating = self.select_power_rating(p_r * 2)
            package = self.select_package(rating)
            p_r_text = (
                f"{self.format_value(p_r, 'W', 'mW')} (需 ≥{rating}W)\n"
                f"建议 1×{package} ({rating}W)"
            )
        else:
            p_r_text = "0 W (无需电阻)"

        # 更新结果
        self.set_cell_value(self.result_r, r_text)
        self.set_cell_value(self.result_p_ldo, self.format_value(p_ldo, "W", "mW"))
        if no_resistor:
            self.set_cell_value(self.result_v_r, "0 V (全部由 LDO 承担)")
        else:
            self.set_cell_value(self.result_v_r, f"{self.format_value(v_r, 'V')}  @ {current_ma:.0f}mA")
        self.set_cell_value(self.result_delta_t, f"{delta_t:.1f} °C")
        self.set_cell_value(self.result_p_r, p_r_text)
        self.set_cell_value(self.result_tj, f"{tj:.1f} °C  (环境 {tamb:.0f}°C)")
        self.set_cell_value(
            self.result_pin,
            f"{self.format_value(p_in, 'W', 'mW')}  (总损耗 {self.format_value(p_loss, 'W', 'mW')})",
        )
        self.set_cell_value(self.result_eff, f"{efficiency:.1f}%")

        # 保存当前数据供 AI 分析使用
        self.last_data = {
            "mode": "无串联电阻 (LDO 全压降)" if no_resistor else "串联电阻降压",
            "model": self.model_combo.currentText(),
            "vin": vin, "vout": vout, "vdrop": vdrop,
            "i_ma": current_ma, "iq_ma": iq,
            "tamb": tamb, "rthja": rthja,
            "r_text": r_text, "p_r_text": p_r_text,
            "r_value": r, "p_r": p_r,
            "p_ldo": p_ldo, "delta_t": delta_t, "tj": tj,
            "p_in": p_in, "p_loss": p_loss, "efficiency": efficiency,
        }

        # 检查警告
        self.check_warnings(current_ma, tj, p_r, p_ldo, derate)

    # ==================== DeepSeek AI 分析 ====================
    def analyze_with_ai(self):
        """调用 DeepSeek 分析当前计算结果 (结果在独立弹窗显示)"""
        if not hasattr(self, "last_data"):
            dialog = DeepSeekDialog(self)
            dialog.set_message("⚠ 请先完成一次有效计算, 再进行 AI 分析。")
            dialog.show()
            return

        # API Key 从 config.json 的 power_conversion.api 中读取
        api_cfg = load_api_config(self.cfg)
        api_key = api_cfg["api_key"]
        if not api_key:
            dialog = DeepSeekDialog(self)
            dialog.set_message(
                "⚠ 未配置 DeepSeek API Key。\n\n"
                "请在 config.json 的 power_conversion.api.api_key 字段中填写 "
                "(platform.deepseek.com 申请)。"
            )
            dialog.show()
            return

        # 独立结果窗口
        dialog = DeepSeekDialog(self)
        dialog.set_message("⏳ 正在请求 DeepSeek 分析, 请稍候 (约 10~30 秒)...")
        dialog.show()

        self.ai_dialog = dialog
        self.ai_thread = DeepSeekThread(
            api_key,
            self.build_ai_prompt(),
            base_url=api_cfg["base_url"],
            model=api_cfg["model"],
            temperature=api_cfg["temperature"],
            max_tokens=api_cfg["max_tokens"],
        )
        self.ai_thread.succeeded.connect(lambda t: self.on_ai_succeeded(dialog, t))
        self.ai_thread.failed.connect(lambda e: self.on_ai_failed(dialog, e))
        self.ai_thread.finished.connect(self.ai_thread.deleteLater)
        self.ai_thread.start()

    def on_ai_succeeded(self, dialog, text):
        """AI 分析成功 (按 Markdown 渲染)"""
        if dialog.isVisible():
            dialog.set_markdown(text)
        self.show_op_message("🤖 DeepSeek 分析完成。", "#409EFF")

    def on_ai_failed(self, dialog, error):
        """AI 分析失败"""
        if dialog.isVisible():
            dialog.set_message(f"❌ DeepSeek 请求失败:\n{error}")
        self.show_op_message("❌ DeepSeek 请求失败, 请检查 API Key 与网络。", "#F56C6C")

    def build_ai_prompt(self):
        """根据当前计算数据生成 AI 分析提示词"""
        d = self.last_data
        warn = self.warn_label.text().strip()

        # 电阻选型上下文: 封装表 + 当前参考方案 (供 AI 推荐具体组合)
        pkg_info = ", ".join(
            f"{k}({v['w']}W)"
            for k, v in self.PACKAGES.items()
        )
        plan_text = ""
        if d.get("p_r", 0) > 0:
            rv = d.get("r_value")
            r_desc = (
                f"{self.format_value(rv, 'Ω')} (E24 推荐 "
                f"{self.format_value(self.nearest_e24(rv), 'Ω')})" if rv else "无"
            )
            plan_text = (
                "【电阻选型】\n"
                f"- 串联电阻阻值: {r_desc}\n"
                f"- 电阻实际功耗: {self.format_value(d['p_r'], 'W', 'mW')} (留 2 倍余量后需 ≥"
                f"{self.select_power_rating(d['p_r'] * 2)}W)\n"
                f"- 可选封装(额定功率): {pkg_info}\n"
                f"- 参考单颗方案: {d['p_r_text'].replace(chr(10), ', ')}\n"
                f"- 参考并联替代: {self.suggest_resistor_plan(d['p_r'])}\n\n"
                "请结合以上数据推荐最合理的电阻组合方案: 对比单颗大封装与多颗小封装并联 "
                "(如 2×1206、4×0805 等), 给出具体封装、数量、每颗功耗, 并说明成本与 "
                "PCB 空间取舍, 最终给出明确推荐。\n\n"
            )

        return (
            "请对以下 LDO 降压电路的计算结果进行分析, 输出:\n"
            "1) 设计是否安全可靠\n"
            "2) 关键风险点\n"
            "3) 具体的改进建议 (如散热措施、电阻调整、芯片选型等)\n"
            "4) 最终结论\n\n"
            "【电路参数】\n"
            f"- 降压方式: {d['mode']}\n"
            f"- 稳压器型号: {d['model']}\n"
            f"- 输入电压: {d['vin']:.2f} V\n"
            f"- 输出电压: {d['vout']:.2f} V\n"
            f"- LDO 最小压降: {d['vdrop']:.2f} V\n"
            f"- 负载电流: {d['i_ma']:.1f} mA\n"
            f"- 静态电流: {d['iq_ma']:.4f} mA\n"
            f"- 环境温度: {d['tamb']:.1f} °C\n"
            f"- 热阻 RθJA: {d['rthja']:.0f} °C/W\n\n"
            "【计算结果】\n"
            f"- 串联电阻: {d['r_text'].replace(chr(10), ', ')}\n"
            f"- 电阻功率: {d['p_r_text'].replace(chr(10), ', ')}\n"
            f"- LDO 功耗: {self.format_value(d['p_ldo'], 'W', 'mW')}\n"
            f"- 温升 ΔT: {d['delta_t']:.1f} °C\n"
            f"- 结温 Tj: {d['tj']:.1f} °C\n"
            f"- 输入功率: {self.format_value(d['p_in'], 'W', 'mW')}\n"
            f"- 总损耗: {self.format_value(d['p_loss'], 'W', 'mW')}\n"
            f"- 效率: {d['efficiency']:.1f} %\n\n"
            + plan_text
            + "【降额/警告检查】\n"
            + f"{warn if warn else '无'}"
        )

    def check_warnings(self, current_ma, tj, p_r, p_ldo, derate):
        """检查过流/降额/过热警告"""
        name = self.model_combo.currentText()
        imax = self.REGULATORS.get(name, self.REGULATORS["自定义"])["imax"]

        derate_limit = imax * derate  # 降额后的安全电流限值
        need_imax = current_ma / derate  # 满足降额要求所需的最小芯片电流

        warnings = []
        if current_ma > imax:
            warnings.append(
                f"🚫 严重过流: 负载 {current_ma:.0f}mA 超过芯片绝对最大电流 {imax}mA, "
                f"芯片会损坏, 禁止使用!"
            )
        elif current_ma > derate_limit:
            warnings.append(
                f"🚫 超出降额限值: 负载 {current_ma:.0f}mA > {derate*100:.0f}% 降额电流 "
                f"{derate_limit:.0f}mA, 该 {imax}mA 芯片不可用!\n"
                f"请更换电流等级 ≥ {need_imax:.0f}mA 的芯片(如 "
                f"{self.suggest_bigger_regulator(need_imax)})。"
            )
        else:
            warnings.append(
                f"✅ 电流降额合格: 负载 {current_ma:.0f}mA ≤ 降额限值 {derate_limit:.0f}mA "
                f"(占额定 {imax}mA 的 {current_ma/imax*100:.0f}%)。"
            )
        if tj > 150:
            warnings.append(f"🔥 严重过热: 结温 {tj:.0f}°C 超过极限 150°C, 器件将损坏! 必须改善散热。")
        elif tj > 125:
            warnings.append(
                f"⚠ 过热: 结温 {tj:.0f}°C 超过最大结温 125°C! "
                f"建议加装散热片、增大串联电阻或降低输入电压/负载电流。"
            )
        elif tj > 85:
            warnings.append(
                f"⚠ 温度偏高: 结温 {tj:.0f}°C, 长期工作可靠性下降, 建议加强散热。"
            )

        if tj <= 85:
            warnings.append(f"✅ 结温 {tj:.0f}°C 在安全范围内, 无需额外散热措施。")

        if not self.mode_check.isChecked():
            warnings.append(
                "ℹ 无串联电阻模式: LDO 承受全部压降, 功耗与温升显著增大; "
                "如结温超标, 建议改用串联电阻降压或加大散热。"
            )

        self.show_warning("\n".join(warnings), "#E6A23C")

    def suggest_bigger_regulator(self, need_imax):
        """根据所需电流等级推荐更大规格的芯片 (优先同输出电压)"""
        try:
            vout = float(self.vout_edit.text().strip())
        except ValueError:
            vout = None

        candidates = []
        for name, params in self.REGULATORS.items():
            if name == "自定义":
                continue
            if params["imax"] >= need_imax and abs(params["vout"] - (vout or 0)) < 0.01:
                candidates.append((name, params["imax"]))
        if candidates:
            candidates.sort(key=lambda x: x[1])
            return candidates[0][0]

        # 无同电压型号时, 选任意更大电流的芯片
        for name, params in self.REGULATORS.items():
            if name == "自定义":
                continue
            if params["imax"] >= need_imax:
                return name
        return "更大电流等级"

    # ==================== 参数持久化 (config.json) ====================
    def save_defaults(self):
        """保存当前参数为默认值 (写入 config.json, 下次启动自动加载)"""
        defaults = self.cfg.config.setdefault("power_conversion", {}).setdefault("defaults", {})
        defaults["model_index"] = self.model_combo.currentIndex()
        defaults["vin"] = self.vin_edit.text().strip()
        defaults["current_ma"] = self.current_edit.text().strip()
        defaults["derate"] = self.derate_edit.text().strip()
        defaults["tamb"] = self.tamb_edit.text().strip()
        defaults["rthja"] = self.rthja_edit.text().strip()
        defaults["iq"] = self.iq_edit.text().strip()
        self.cfg.save_config()

        self.show_op_message(
            "💾 已保存为默认参数并写入 config.json: 型号、输入电压、负载电流、"
            "降额系数、环境温度、热阻、静态电流将在下次启动时自动加载。",
            "#67C23A"
        )

    def load_defaults(self):
        """从 config.json 加载默认参数"""
        defaults = self.cfg.config.get("power_conversion", {}).get("defaults", {})

        # 先恢复型号 (会触发参数自动填充), 再覆盖用户保存的值
        model_index = defaults.get("model_index", 0)
        if isinstance(model_index, (int, float)) and 0 <= int(model_index) < self.model_combo.count():
            self.model_combo.setCurrentIndex(int(model_index))

        pairs = [
            (self.vin_edit, str(defaults.get("vin", "12"))),
            (self.current_edit, str(defaults.get("current_ma", "100"))),
            (self.derate_edit, str(defaults.get("derate", "80"))),
            (self.tamb_edit, str(defaults.get("tamb", "25"))),
            (self.rthja_edit, str(defaults.get("rthja", ""))),
            (self.iq_edit, str(defaults.get("iq", ""))),
        ]
        for edit, value in pairs:
            if value:
                edit.setText(value)

    def restore_factory_defaults(self):
        """恢复默认参数: 仅恢复参数输入, 不改变当前选择的元器件型号"""
        factory = self.cfg.get_factory_defaults()["power_conversion"]["defaults"]
        defaults = self.cfg.config.setdefault("power_conversion", {}).setdefault("defaults", {})
        # 恢复出厂默认值, 但保留当前选择的型号
        current_model = self.model_combo.currentIndex()
        for k, v in factory.items():
            defaults[k] = v
        defaults["model_index"] = current_model
        self.cfg.save_config()

        # 型号保持不变, 只恢复参数输入
        self.vin_edit.setText(str(factory.get("vin", "12")))
        self.current_edit.setText(str(factory.get("current_ma", "100")))
        self.derate_edit.setText(str(factory.get("derate", "80")))
        self.tamb_edit.setText(str(factory.get("tamb", "25")))

        # rthja / iq 恢复为当前型号参数
        self.on_regulator_changed(self.model_combo.currentIndex())

        # 强制刷新计算: setText 在文本未变化时不触发 textChanged,
        # 需手动调用, 否则结果区/警告区不会更新
        self.calculate()
        self.show_op_message("↺ 已恢复默认参数 (元器件型号保持不变)。", "#67C23A")

    def show_warning(self, text, color="#E6A23C"):
        """显示警告信息"""
        self.warn_label.setStyleSheet(
            f"color: {color}; background: #FDF6EC; border: 1px solid {color};"
            "border-radius: 6px; padding: 10px;"
        )
        self.warn_label.setText(text)

    def show_op_message(self, text, color="#67C23A"):
        """显示底部操作提示 (保存/恢复默认等)"""
        if not hasattr(self, "op_msg_label"):
            return
        self.op_msg_label.setStyleSheet(
            f"color: {color}; background: #F0F9EB; border: 1px solid {color};"
            "border-radius: 6px; padding: 8px 12px;"
        )
        self.op_msg_label.setText(text)

    def clear_result(self):
        """清空结果"""
        for label in (self.result_r, self.result_p_ldo, self.result_v_r,
                      self.result_delta_t, self.result_p_r, self.result_tj,
                      self.result_pin, self.result_eff):
            self.set_cell_value(label, "—")

    # ==================== 工具函数 ====================
    def nearest_e24(self, r):
        """获取最接近的 E24 标准阻值"""
        if r <= 0:
            return 0
        decade = 10 ** math.floor(math.log10(r))
        mantissa = r / decade
        best = min(self.E24, key=lambda x: abs(x - mantissa))
        return best * decade

    def select_power_rating(self, p):
        """选择标准功率等级 (留 2 倍余量)"""
        for rating in self.POWER_RATINGS:
            if p <= rating:
                return rating
        return 10

    def select_package(self, rating):
        """根据功率等级推荐单颗电阻封装"""
        if rating <= 0.125:
            return "0603"
        if rating <= 0.25:
            return "0805"
        if rating <= 0.5:
            return "1206"
        if rating <= 1:
            return "2512"
        if rating <= 2:
            return "大功率贴片"
        return "插件绕线电阻"

    def suggest_resistor_plan(self, p_r):
        """生成电阻选型方案: 单颗大封装 vs 多颗小封装并联, 对比成本与 PCB 空间
        例如 1W 场景: 1×2512 或 4×1206 并联 (每颗 0.25W)"""
        if p_r <= 0:
            return "无需电阻"
        p_need = p_r * 2  # 留 2 倍功率余量
        rating = self.select_power_rating(p_need)
        single_pkg = self.select_package(rating)
        single = self.PACKAGES.get(single_pkg)
        base = f"1×{single_pkg} ({rating}W)"

        # 评估小封装并联方案: n 颗, 每颗承担 p_need/n, 2~8 颗为合理范围
        best = None
        for pkg in self.PARALLEL_PACKAGES:
            info = self.PACKAGES[pkg]
            n = math.ceil(p_need / info["w"])
            if not (2 <= n <= 8):
                continue
            cost = n * info["price"]
            area = n * info["area"]
            if best is None or (cost, area) < (best[3], best[4]):
                best = (pkg, n, info["w"], cost, area)
        if best is None or single is None:
            return base

        pkg, n, pw, cost, area = best
        scost, sarea = single["price"], single["area"]
        tags = []
        if cost <= scost * 0.95 and area <= sarea * 0.9:
            tags.append("更便宜更省空间")
        elif cost <= scost * 0.95:
            tags.append("更便宜")
        elif area <= sarea * 0.9:
            tags.append("更省空间")
        else:
            tags.append("成本/空间略增")
        return f"{base} | 替代 {n}×{pkg} 并联, 每颗 {pw}W ({','.join(tags)})"

    def format_value(self, value, unit, small_unit=None):
        """格式化数值, 自动进行单位换算"""
        if value == 0:
            return f"0 {unit}"
        if value < 0.001:
            if small_unit:
                return f"{value * 1000:.2f} {small_unit}"
            return f"{value:.4g} {unit}"
        if value < 1 and small_unit:
            return f"{value * 1000:.2f} {small_unit}"
        if value >= 1000000:
            return f"{value / 1000000:.2f} M{unit}"
        if value >= 1000:
            return f"{value / 1000:.2f} k{unit}"
        return f"{value:.2f} {unit}"

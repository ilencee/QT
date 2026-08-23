"""
硬件工具箱: 硬件工程师常用计算工具集合 (Tab 聚合页)

包含 7 个计算工具 (全部离线本地计算, 无网络依赖):
1. DC-DC BUCK 开关电源: 占空比 / 电感 / 纹波 / 输出电容 / 续流二极管选型
2. 散热与功耗: 功耗换算 / 温升 / 结温 / 散热器热阻反推 (MOSFET / 三极管器件库)
3. 分压偏置驱动: ADC 分压 / LED 限流 / 三极管开关 / 上拉下拉
4. 晶振匹配电容: 负载电容 C1/C2 / 频偏估算
5. PCB 走线: IPC-2221 载流与线宽互算 / 走线电阻与压降
6. 电池续航: mAh/Wh 换算 / 多模式加权续航 / 充电时间
7. 波特率/定时器: MCU 定时周期 / 8051 串口波特率 / PWM 频率占空比

交互风格沿用功率变换页: 实时计算 (textChanged 直连) + 卡片式 UI + 温和错误提示。
"""

import math
from pathlib import Path

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QFrame, QLabel,
    QComboBox, QLineEdit, QFormLayout, QGridLayout, QSizePolicy,
    QTabWidget, QStackedWidget, QDoubleSpinBox, QPushButton,
    QScrollArea,
)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QFont, QDoubleValidator

from app.core.config_manager import ConfigManager, app_root

# 统一输入控件样式 (与功率变换页一致)
_INPUT_QSS = """
    QLineEdit {
        background: #FFFFFF; border: 1px solid #DCDFE6;
        border-radius: 6px; padding: 4px 10px;
        font-family: "Microsoft YaHei"; font-size: 10pt; color: #303133;
    }
    QLineEdit:hover { border-color: #C0C4CC; }
    QLineEdit:focus { border: 1px solid #007AFF; }
    QComboBox {
        background: #FFFFFF; border: 1px solid #DCDFE6;
        border-radius: 6px; padding: 4px 10px;
        font-family: "Microsoft YaHei"; font-size: 10pt; color: #303133;
    }
    QComboBox:hover { border-color: #C0C4CC; }
    QComboBox:focus { border: 1px solid #007AFF; }
    QComboBox::drop-down { border: none; width: 26px; }
    QComboBox QAbstractItemView {
        background: #FFFFFF; border: 1px solid #DCDFE6;
        selection-background-color: #E8F2FF; selection-color: #007AFF;
        font-family: "Microsoft YaHei"; font-size: 10pt;
    }
"""

# Tab 聚合页样式: macOS 风格 Tab 栏 (accent 下划线指示当前项)
_TAB_QSS = """
    QTabWidget::pane {
        border: 1px solid #E5E5EA; border-radius: 10px;
        background: #FFFFFF; top: -1px;
    }
    QTabBar::tab {
        background: transparent; padding: 9px 20px;
        margin-right: 4px; color: #6E6E73;
        font-family: "Microsoft YaHei"; font-size: 11pt;
        border-bottom: 3px solid transparent;
    }
    QTabBar::tab:hover { color: #007AFF; }
    QTabBar::tab:selected {
        color: #007AFF; border-bottom: 3px solid #007AFF; font-weight: bold;
    }
    QTabBar::tab:first { padding-left: 14px; }
"""


# E12 标准电感值系列 (µH): 就近取值
_E12_IND = [1.0, 1.2, 1.5, 1.8, 2.2, 2.7, 3.3, 3.9, 4.7, 5.6, 6.8,
            8.2, 10, 12, 15, 18, 22, 27, 33, 39, 47, 56, 68, 82, 100,
            120, 150, 180, 220, 270, 330, 390, 470, 560, 680, 820, 1000]


def _nearest_std(value, series):
    """取标准值系列中最接近的值"""
    if value is None:
        return None
    return min(series, key=lambda s: abs(s - value))


class _CalcTab(QWidget):
    """计算 Tab 共用基类: 卡片构建辅助 + 数值格式化 + 器件库配置覆盖"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.cfg = ConfigManager(str(app_root() / "config.json"))
        self.setStyleSheet(_INPUT_QSS)

    # ==================== 器件库配置覆盖 ====================
    def _load_lib(self, key, defaults):
        """读取 config.json 中 hardware_toolbox.<key> 器件库, 缺省回退代码内置;
        仅当 hardware_toolbox 配置段缺失时才写盘一次 (避免每次进入页面全量 dump)"""
        if "hardware_toolbox" not in self.cfg.config:
            self.cfg.config["hardware_toolbox"] = {}
            self.cfg.save_config()
        lib = self.cfg.config.get("hardware_toolbox", {}).get(key)
        return lib if lib else dict(defaults)

    # ==================== 数值工具 ====================
    @staticmethod
    def num(text):
        """安全解析数字, 无效返回 None"""
        try:
            v = float(str(text).strip())
            return v
        except (ValueError, AttributeError, TypeError):
            return None

    @staticmethod
    def fmt(v, unit="", sig=4):
        """格式化数值: 3-4 位有效数字 + 单位; None/NaN/inf 返回 '--'"""
        if v is None:
            return "--"
        try:
            v = float(v)
        except (TypeError, ValueError):
            return "--"
        if v != v or v in (float("inf"), float("-inf")):
            return "--"
        a = abs(v)
        if a == 0:
            s = "0"
        elif a >= 100000 or a < 0.0001:
            s = f"{v:.2e}"
        else:
            s = f"{v:.{sig}g}"
        return s + unit

    # ==================== 视觉辅助 ====================
    def _card_title(self, text, icon):
        """统一卡片标题: accent 蓝竖条 + 图标 + 文字"""
        bar = QFrame()
        bar.setFixedSize(4, 20)
        bar.setStyleSheet("background: #007AFF; border-radius: 2px;")
        label = QLabel(f"{icon}  {text}")
        label.setFont(QFont("Microsoft YaHei", 14, QFont.Weight.Bold))
        label.setStyleSheet("color: #1D1D1F;")
        h = QHBoxLayout()
        h.setSpacing(8)
        h.addWidget(bar)
        h.addWidget(label)
        h.addStretch()
        wrap = QWidget()
        wrap.setLayout(h)
        return wrap

    def _form_row(self, form, text, widget):
        """向表单添加统一样式的行 (标签灰色)"""
        label = QLabel(text)
        label.setFont(QFont("Microsoft YaHei", 10))
        label.setStyleSheet("color: #6E6E73;")
        form.addRow(label, widget)

    def _create_edit(self, default="0", callback=None, allow_negative=False,
                     max_v=1000000.0, tooltip=""):
        """创建带数字校验的输入框 (textChanged 实时回调)"""
        edit = QLineEdit(str(default))
        edit.setMinimumHeight(34)
        edit.setAlignment(Qt.AlignmentFlag.AlignRight)
        lo = -1e9 if allow_negative else 0.0
        validator = QDoubleValidator(lo, max_v, 6)
        validator.setNotation(QDoubleValidator.Notation.StandardNotation)
        edit.setValidator(validator)
        if callback is not None:
            edit.textChanged.connect(callback)
        if tooltip:
            edit.setToolTip(tooltip)
        return edit

    def _create_combo(self, items, callback=None, tooltip=""):
        """创建下拉框 (可选 callback)"""
        combo = QComboBox()
        combo.setMinimumHeight(34)
        combo.addItems(list(items))
        if callback is not None:
            combo.currentIndexChanged.connect(callback)
        if tooltip:
            combo.setToolTip(tooltip)
        return combo

    def create_result_cell(self, grid, row, col, title, color):
        """创建结果小卡片 (富文本 QLabel, 换行自动撑高)"""
        label = QLabel()
        label.setWordWrap(True)
        label.setTextFormat(Qt.TextFormat.RichText)
        label.setMinimumHeight(46)
        label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        label.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Minimum)
        label.setStyleSheet(
            "QLabel { background: #F5F7FA; border-radius: 6px; padding: 6px 10px; }"
        )
        label.setProperty("cell_title", title)
        label.setProperty("cell_color", color)
        label.setText(self.cell_html(title, "--", color))
        grid.addWidget(label, row, col)
        return label

    @staticmethod
    def cell_html(title, value, color):
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

    def clear_results(self, *labels):
        """清空结果格"""
        for label in labels:
            self.set_cell_value(label, "--")

    def set_warn(self, text, color="#E6A23C"):
        """温和错误/警告提示 (不弹窗)"""
        if not hasattr(self, "warn_label"):
            return
        self.warn_label.setStyleSheet(
            f"color: {color}; background: #FDF6EC; border: 1px solid {color};"
            "border-radius: 6px; padding: 8px 10px;"
        )
        self.warn_label.setText(text)

    def clear_warn(self):
        self.set_warn(" ")

    def _result_grid(self, layout, cols=2):
        """创建 2 列结果网格"""
        grid = QGridLayout()
        grid.setSpacing(10)
        grid.setColumnStretch(0, 1)
        grid.setColumnStretch(1, 1)
        layout.addLayout(grid)
        return grid

    def _formula_note(self, lines):
        """创建公式说明块 (返回 QLabel, 由调用方 addWidget)"""
        note = QLabel("\n".join(lines))
        note.setFont(QFont("Microsoft YaHei", 9))
        note.setStyleSheet(
            "color: #6E6E73; background: #F5F7FA; border-radius: 6px;"
            "padding: 6px 10px;"
        )
        return note


# =====================================================================
# Tab 1: DC-DC BUCK 开关电源计算
# =====================================================================
class DcdcBuckTab(_CalcTab):
    """DC-DC BUCK 降压计算: 占空比 / 电感 / 纹波 / 输出电容 / 续流二极管"""

    # 常用 BUCK 控制芯片器件库 (config.json hardware_toolbox.dcdc_chips 可覆盖)
    # 字段: fsw_khz=典型开关频率, vin_max=最高输入, type=拓扑
    DEFAULT_CHIPS = {
        "TPS5430 (SWIFT, 3A)":        {"fsw_khz": 500, "vin_max": 36, "iout_max": 3.0},
        "TPS562200 (SOT-23-6, 2A)":   {"fsw_khz": 580, "vin_max": 17, "iout_max": 2.0},
        "LM2596-ADJ (TO-263, 3A)":    {"fsw_khz": 150, "vin_max": 40, "iout_max": 3.0},
        "MP1584 (SOT-23-8, 3A)":      {"fsw_khz": 1500, "vin_max": 28, "iout_max": 3.0},
        "MP2315 (SOT-23-8, 3A)":      {"fsw_khz": 500, "vin_max": 24, "iout_max": 3.0},
        "XL4015 (TO-263, 5A)":        {"fsw_khz": 180, "vin_max": 36, "iout_max": 5.0},
        "XL6009 (TO-263, 4A 升降压)":  {"fsw_khz": 400, "vin_max": 32, "iout_max": 4.0},
        "自定义":                      {"fsw_khz": 200, "vin_max": 24, "iout_max": 2.0},
    }

    def __init__(self, parent=None):
        super().__init__(parent)
        self.chips = self._load_lib("dcdc_chips", self.DEFAULT_CHIPS)
        self.initUI()

    def initUI(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(16)

        main = QHBoxLayout()
        main.setSpacing(16)
        main.addWidget(self._input_card())
        main.addWidget(self._result_card(), 1)
        layout.addLayout(main)

        self.warn_label = QLabel(" ")
        self.warn_label.setWordWrap(True)
        self.warn_label.setStyleSheet(
            "color: #E6A23C; background: #FDF6EC; border: 1px solid #E6A23C;"
            "border-radius: 6px; padding: 8px 10px;"
        )
        layout.addWidget(self.warn_label)
        self.clear_warn()

        self.calculate()

    def _input_card(self):
        frame = QFrame()
        frame.setObjectName("card")
        frame.setFixedWidth(320)
        v = QVBoxLayout(frame)
        v.setContentsMargins(20, 20, 20, 20)
        v.setSpacing(10)
        v.addWidget(self._card_title("参数输入", "⚙️"))

        v.addWidget(QLabel("BUCK 控制芯片"))
        self.chip_combo = self._create_combo(
            list(self.chips.keys()), self._on_chip_changed,
            tooltip="选择常用芯片自动填充开关频率"
        )
        v.addWidget(self.chip_combo)

        form = QFormLayout()
        form.setSpacing(9)
        form.setLabelAlignment(Qt.AlignmentFlag.AlignRight)

        self.vin_edit = self._create_edit("12", self.calculate, tooltip="输入电压 Vin")
        self._form_row(form, "输入电压 Vin (V):", self.vin_edit)

        self.vout_edit = self._create_edit("5", self.calculate, tooltip="输出电压 Vout")
        self._form_row(form, "输出电压 Vout (V):", self.vout_edit)

        self.iout_edit = self._create_edit("2", self.calculate, tooltip="最大负载电流")
        self._form_row(form, "负载电流 Iout (A):", self.iout_edit)

        self.fsw_edit = self._create_edit("200", self.calculate, tooltip="开关频率, 常用 150~1500 kHz")
        self._form_row(form, "开关频率 fsw (kHz):", self.fsw_edit)

        self.ripple_edit = self._create_edit("30", self.calculate,
                                             tooltip="电感纹波系数, 推荐 20%~40% (本工具取 30%)")
        self._form_row(form, "纹波系数 ΔI/Iout (%):", self.ripple_edit)

        self.dvout_edit = self._create_edit("50", self.calculate,
                                            tooltip="目标输出纹波电压 (峰峰值)")
        self._form_row(form, "目标纹波 ΔVout (mV):", self.dvout_edit)

        self.vd_edit = self._create_edit("0.5", self.calculate,
                                         tooltip="续流二极管正向压降, 肖特基约 0.4~0.6V")
        self._form_row(form, "二极管压降 Vd (V):", self.vd_edit)

        v.addLayout(form)

        live = QLabel("🔄 实时计算: 修改参数后结果自动更新")
        live.setFont(QFont("Microsoft YaHei", 9))
        live.setStyleSheet(
            "color: #67C23A; background: #F0F9EB; border-radius: 4px;"
            "padding: 6px 8px;"
        )
        v.addWidget(live)
        v.addStretch()

        self._on_chip_changed(0)
        return frame

    def _on_chip_changed(self, index):
        """芯片型号切换 → 自动填充开关频率"""
        name = self.chip_combo.currentText()
        params = self.chips.get(name) or self.chips.get("自定义", {})
        self.fsw_edit.setText(str(params.get("fsw_khz", 200)))

    def _result_card(self):
        frame = QFrame()
        frame.setObjectName("card")
        v = QVBoxLayout(frame)
        v.setContentsMargins(20, 16, 20, 16)
        v.setSpacing(10)
        v.addWidget(self._card_title("计算结果", "📊"))

        diagram = QLabel("Vin ──[SW]──▶ 二极管▽  ──▶ Vout\n        [L]")
        diagram.setFont(QFont("Consolas", 10))
        diagram.setAlignment(Qt.AlignmentFlag.AlignCenter)
        diagram.setStyleSheet(
            "color: #007AFF; background: #F0F7FF; padding: 6px;"
            "border-radius: 6px; font-weight: bold;"
        )
        v.addWidget(diagram)

        grid = self._result_grid(v)
        self.r_duty = self.create_result_cell(grid, 0, 0, "占空比 D", "#007AFF")
        self.r_l = self.create_result_cell(grid, 0, 1, "电感 L (µH)", "#409EFF")
        self.r_lstd = self.create_result_cell(grid, 1, 0, "推荐标准电感", "#67C23A")
        self.r_di = self.create_result_cell(grid, 1, 1, "纹波电流 ΔIL (A)", "#E6A23C")
        self.r_ipeak = self.create_result_cell(grid, 2, 0, "电感峰值电流 (A)", "#F56C6C")
        self.r_cout = self.create_result_cell(grid, 2, 1, "输出电容 Cout (µF)", "#409EFF")
        self.r_vr = self.create_result_cell(grid, 3, 0, "输出纹波估算 (mV)", "#E6A23C")
        self.r_id = self.create_result_cell(grid, 3, 1, "二极管平均电流 (A)", "#F56C6C")

        v.addWidget(self._formula_note([
            "计算说明",
            "• 占空比 D = Vout / Vin (CCM 连续导通模式)",
            "• 纹波电流 ΔIL = 纹波系数% × Iout,  电感 L = (Vin−Vout)×D / (fsw×ΔIL)",
            "• 输出电容 Cout ≈ ΔIL / (8×fsw×ΔVout)   (忽略 ESR)",
            "• 二极管反向耐压 ≥ Vin,  平均电流 ≈ Iout×(1−D)",
        ]))
        return frame

    def calculate(self):
        if not hasattr(self, "r_duty"):
            return
        vin = self.num(self.vin_edit.text())
        vout = self.num(self.vout_edit.text())
        iout = self.num(self.iout_edit.text())
        fsw_khz = self.num(self.fsw_edit.text())
        ripple = self.num(self.ripple_edit.text())
        dvout_mv = self.num(self.dvout_edit.text())
        vd = self.num(self.vd_edit.text())

        labels = (self.r_duty, self.r_l, self.r_lstd, self.r_di,
                  self.r_ipeak, self.r_cout, self.r_vr, self.r_id)
        if None in (vin, vout, iout, fsw_khz, ripple, dvout_mv, vd):
            self.clear_results(*labels)
            self.set_warn("请输入有效的数字!", "#F56C6C")
            return
        if vin <= 0 or vout <= 0 or iout <= 0 or fsw_khz <= 0 or vd < 0:
            self.clear_results(*labels)
            self.set_warn("电压、电流、频率必须大于 0!", "#F56C6C")
            return
        if vout >= vin:
            self.clear_results(*labels)
            self.set_warn("BUCK 降压电路要求 Vout < Vin!", "#F56C6C")
            return
        if not (5 <= ripple <= 60):
            self.clear_results(*labels)
            self.set_warn("纹波系数建议在 5%~60% 之间 (推荐 20%~40%)", "#E6A23C")
            return

        fsw = fsw_khz * 1000.0
        d = vout / vin                       # 占空比
        delta_i = ripple / 100.0 * iout      # 纹波电流
        l_h = (vin - vout) * d / (fsw * delta_i)   # H
        l_uh = l_h * 1e6
        l_std = _nearest_std(l_uh, _E12_IND)       # 标准值
        i_peak = iout + delta_i / 2.0
        dvout_v = dvout_mv / 1000.0
        cout_f = delta_i / (8 * fsw * dvout_v)     # F
        cout_uf = cout_f * 1e6
        # 用输出电容反推实际纹波 (与目标一致, 保留 ESR 说明)
        vripple_mv = delta_i / (8 * fsw * cout_f) * 1000.0 if cout_f > 0 else 0
        i_d = iout * (1 - d)                       # 二极管平均电流
        v_diode_rev = vin                          # 反向耐压

        self.set_cell_value(self.r_duty, self.fmt(d * 100, "%"))
        self.set_cell_value(self.r_l, self.fmt(l_uh, " µH"))
        self.set_cell_value(self.r_lstd,
                            f"{self.fmt(l_std, ' µH')}\n(就近标准值)")
        self.set_cell_value(self.r_di, self.fmt(delta_i, " A"))
        self.set_cell_value(self.r_ipeak, self.fmt(i_peak, " A"))
        self.set_cell_value(self.r_cout, self.fmt(cout_uf, " µF"))
        self.set_cell_value(self.r_vr, self.fmt(vripple_mv, " mV"))
        self.set_cell_value(self.r_id, self.fmt(i_d, " A"))

        # 越限提醒
        warns = []
        name = self.chip_combo.currentText()
        params = self.chips.get(name)
        if params:
            vin_max = params.get("vin_max")
            iout_max = params.get("iout_max")
            if vin_max and vin > vin_max:
                warns.append(f"⚠ Vin({vin}V) 超过 {name} 最高输入 {vin_max}V!")
            if iout_max and iout > iout_max:
                warns.append(f"⚠ Iout({iout}A) 超过 {name} 额定电流 {iout_max}A!")
        if cout_uf > 2200:
            warns.append("输出电容偏大 (>2200µF), 可降低纹波要求或提高开关频率。")
        if l_uh > 100:
            warns.append("电感偏大 (>100µH), 请检查频率与纹波系数设置。")
        self.set_warn("\n".join(warns) if warns else " ", "#E6A23C" if warns else "#67C23A")
        if not warns:
            self.set_warn(" ✓ 参数在常规范围内", "#67C23A")


# =====================================================================
# Tab 2: 散热与功耗计算
# =====================================================================
class ThermalTab(_CalcTab):
    """散热与功耗: 功耗换算 / 温升 / 结温 / 散热器热阻反推"""

    # 常用功率器件器件库 (config.json hardware_toolbox.thermal_parts 可覆盖)
    # 字段: type=器件类型, rthjc=结-壳热阻, rthja=结-环境热阻(无散热器),
    #       pd=最大功耗, 封装; 贴片优先
    DEFAULT_PARTS = {
        "AO3400 (SOT-23, N-MOS)":   {"type": "MOSFET", "rthjc": 40,  "rthja": 120, "pd": 1.4},
        "AO3401 (SOT-23, P-MOS)":   {"type": "MOSFET", "rthjc": 45,  "rthja": 130, "pd": 1.3},
        "SI2302 (SOT-23, N-MOS)":   {"type": "MOSFET", "rthjc": 35,  "rthja": 110, "pd": 1.5},
        "SI2301 (SOT-23, P-MOS)":   {"type": "MOSFET", "rthjc": 40,  "rthja": 125, "pd": 1.3},
        "IRLR2905 (DPAK, N-MOS)":   {"type": "MOSFET", "rthjc": 2.5, "rthja": 62,  "pd": 42},
        "IRLZ44N (TO-220, N-MOS)":  {"type": "MOSFET", "rthjc": 1.7, "rthja": 62,  "pd": 90},
        "IRF540N (TO-220, N-MOS)":  {"type": "MOSFET", "rthjc": 1.7, "rthja": 62,  "pd": 94},
        "S8050 (SOT-23, NPN)":      {"type": "BJT",    "hfe": 120,  "ic_max": 0.5, "rthja": 200, "pd": 0.3},
        "SS8050 (SOT-23, NPN)":     {"type": "BJT",    "hfe": 120,  "ic_max": 1.5, "rthja": 180, "pd": 0.5},
        "BC817 (SOT-23, NPN)":      {"type": "BJT",    "hfe": 250,  "ic_max": 0.5, "rthja": 220, "pd": 0.3},
        "2N2222A (TO-92, NPN)":     {"type": "BJT",    "hfe": 100,  "ic_max": 0.8, "rthja": 200, "pd": 0.625},
        "TIP41C (TO-220, NPN)":     {"type": "BJT",    "hfe": 30,   "ic_max": 6.0, "rthjc": 1.9, "rthja": 65, "pd": 65},
        "TIP42C (TO-220, PNP)":     {"type": "BJT",    "hfe": 30,   "ic_max": 6.0, "rthjc": 1.9, "rthja": 65, "pd": 65},
        "自定义":                    {"type": "自定义", "rthjc": 5.0, "rthja": 100, "pd": 10},
    }

    def __init__(self, parent=None):
        super().__init__(parent)
        self.parts = self._load_lib("thermal_parts", self.DEFAULT_PARTS)
        self.initUI()

    def initUI(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(16)

        main = QHBoxLayout()
        main.setSpacing(16)
        main.addWidget(self._input_card())
        main.addWidget(self._result_card(), 1)
        layout.addLayout(main)

        self.warn_label = QLabel(" ")
        self.warn_label.setWordWrap(True)
        self.warn_label.setStyleSheet(
            "color: #E6A23C; background: #FDF6EC; border: 1px solid #E6A23C;"
            "border-radius: 6px; padding: 8px 10px;"
        )
        layout.addWidget(self.warn_label)
        self.clear_warn()

        self.calculate()

    def _input_card(self):
        frame = QFrame()
        frame.setObjectName("card")
        frame.setFixedWidth(320)
        v = QVBoxLayout(frame)
        v.setContentsMargins(20, 20, 20, 20)
        v.setSpacing(10)
        v.addWidget(self._card_title("参数输入", "⚙️"))

        v.addWidget(QLabel("功率器件"))
        self.part_combo = self._create_combo(
            list(self.parts.keys()), self._on_part_changed,
            tooltip="选择器件自动填充热阻 (贴片优先)"
        )
        v.addWidget(self.part_combo)

        form = QFormLayout()
        form.setSpacing(9)
        form.setLabelAlignment(Qt.AlignmentFlag.AlignRight)

        self.power_edit = self._create_edit("1", self.calculate,
                                            tooltip="器件功耗 (若填写 V×I 将自动覆盖此值)")
        self._form_row(form, "功耗 P (W):", self.power_edit)

        self.volt_edit = self._create_edit("", self.calculate, tooltip="电压 (可选, 与电流一起自动算功耗)")
        self._form_row(form, "电压 V (V):", self.volt_edit)

        self.cur_edit = self._create_edit("", self.calculate, tooltip="电流 (可选, 与电压一起自动算功耗)")
        self._form_row(form, "电流 I (A):", self.cur_edit)

        self.ta_edit = self._create_edit("25", self.calculate, allow_negative=True,
                                         tooltip="环境温度, 可填负值 (低温环境)")
        self._form_row(form, "环境温度 Ta (°C):", self.ta_edit)

        self.tjmax_edit = self._create_edit("150", self.calculate,
                                            tooltip="器件最大允许结温: MOSFET 一般 150°C, 三极管 125~150°C")
        self._form_row(form, "最大结温 Tj_max (°C):", self.tjmax_edit)

        self.rthjc_edit = self._create_edit("5", self.calculate,
                                            tooltip="结-壳热阻 RθJC (°C/W)")
        self._form_row(form, "RθJC (°C/W):", self.rthjc_edit)

        self.rthcs_edit = self._create_edit("0.5", self.calculate,
                                            tooltip="壳-散热器热阻 RθCS, 加硅脂约 0.5, 无散热器可不计")
        self._form_row(form, "RθCS (°C/W):", self.rthcs_edit)

        self.rthsa_edit = self._create_edit("", self.calculate,
                                            tooltip="散热器热阻 RθSA (°C/W). 留空=按无散热器反推所需值")
        self._form_row(form, "散热器 RθSA (°C/W):", self.rthsa_edit)

        v.addLayout(form)

        mode_note = QLabel("💡 散热路径: RθJC + RθCS + RθSA (无散热器时近似 RθJA)")
        mode_note.setFont(QFont("Microsoft YaHei", 9))
        mode_note.setWordWrap(True)
        mode_note.setStyleSheet(
            "color: #6E6E73; background: #F5F7FA; border-radius: 4px;"
            "padding: 6px 8px;"
        )
        v.addWidget(mode_note)
        v.addStretch()

        self._on_part_changed(0)
        return frame

    def _on_part_changed(self, index):
        """器件型号切换 → 自动填充热阻"""
        name = self.part_combo.currentText()
        params = self.parts.get(name) or self.parts.get("自定义", {})
        self.rthjc_edit.setText(self.fmt(params.get("rthjc", 5.0)))
        # 有 RθJA 的器件: 无散热器时用 RθJA 作为散热路径参考

    def _result_card(self):
        frame = QFrame()
        frame.setObjectName("card")
        v = QVBoxLayout(frame)
        v.setContentsMargins(20, 16, 20, 16)
        v.setSpacing(10)
        v.addWidget(self._card_title("计算结果", "📊"))

        grid = self._result_grid(v)
        self.r_p = self.create_result_cell(grid, 0, 0, "功耗 P (W)", "#007AFF")
        self.r_rth = self.create_result_cell(grid, 0, 1, "总热阻 Rth (°C/W)", "#409EFF")
        self.r_dt = self.create_result_cell(grid, 1, 0, "温升 ΔT (°C)", "#E6A23C")
        self.r_tj = self.create_result_cell(grid, 1, 1, "结温 Tj (°C)", "#F56C6C")
        self.r_rth_need = self.create_result_cell(grid, 2, 0, "所需散热器 Rth (°C/W)", "#67C23A")
        self.r_verdict = self.create_result_cell(grid, 2, 1, "散热结论", "#409EFF")

        v.addWidget(self._formula_note([
            "计算说明",
            "• 散热路径: RθJC + RθCS + RθSA (无散热器时近似器件 RθJA)",
            "• 温升 ΔT = P × Rth,  结温 Tj = Ta + ΔT",
            "• 所需散热器 = (Tj_max − Ta)/P − RθJC − RθCS",
        ]))
        return frame

    def calculate(self):
        if not hasattr(self, "r_p"):
            return
        p_in = self.num(self.power_edit.text())
        volt = self.num(self.volt_edit.text())
        cur = self.num(self.cur_edit.text())
        ta = self.num(self.ta_edit.text())
        tjmax = self.num(self.tjmax_edit.text())
        rthjc = self.num(self.rthjc_edit.text())
        rthcs = self.num(self.rthcs_edit.text())
        rthsa = self.num(self.rthsa_edit.text())

        labels = (self.r_p, self.r_rth, self.r_dt, self.r_tj,
                  self.r_rth_need, self.r_verdict)
        if None in (ta, tjmax, rthjc, rthcs):
            self.clear_results(*labels)
            self.set_warn("请输入有效的数字!", "#F56C6C")
            return

        # 功耗: 若 V 与 I 都填写则自动计算并覆盖
        if volt is not None and cur is not None:
            p = volt * cur
        else:
            if p_in is None:
                self.clear_results(*labels)
                self.set_warn("请输入功耗 P, 或同时填写电压与电流!", "#F56C6C")
                return
            p = p_in

        if p < 0 or tjmax <= 0 or rthjc <= 0 or rthcs < 0:
            self.clear_results(*labels)
            self.set_warn("功耗、最大结温、热阻必须有效 (P≥0)!", "#F56C6C")
            return

        # 总热阻: 用户填了 RθSA → 分体路径; 留空 → 无散热器近似 RθJA (器件库) 或提示
        name = self.part_combo.currentText()
        params = self.parts.get(name)
        rthja_lib = params.get("rthja") if params else None

        if rthsa is not None and rthsa >= 0:
            rth_total = rthjc + rthcs + rthsa
            has_heatsink = True
        else:
            # 无散热器: 近似用器件 RθJA (一体热阻)
            if rthja_lib:
                rth_total = rthja_lib
                has_heatsink = False
            else:
                # 无 RθJA 数据时退化为结-壳路径
                rth_total = rthjc + rthcs
                has_heatsink = True

        dt = p * rth_total
        tj = ta + dt

        # 所需散热器热阻 (分体路径反推)
        need = (tjmax - ta) / p - rthjc - rthcs if p > 0 else None

        self.set_cell_value(self.r_p, self.fmt(p, " W"))
        self.set_cell_value(self.r_rth, self.fmt(rth_total, " °C/W"))
        self.set_cell_value(self.r_dt, self.fmt(dt, " °C"))
        self.set_cell_value(self.r_tj, self.fmt(tj, " °C"))

        if need is None or need >= 1000:
            self.set_cell_value(self.r_rth_need, "--")
        else:
            self.set_cell_value(self.r_rth_need, self.fmt(max(need, 0), " °C/W"))

        # 结论
        if tj > tjmax:
            if not has_heatsink and rthja_lib:
                verdict = (f"❌ 结温超限!\n建议: 需加散热器 RθSA ≤ {self.fmt(max(need,0),' °C/W')}\n"
                           f"或改用更大封装/降低功耗")
            elif need is not None and need < 0:
                verdict = "❌ 结温超限!\n散热器热阻过小,\n请降低功耗或换散热方案"
            else:
                verdict = f"❌ 结温超限 {self.fmt(tj,'°C')} > {self.fmt(tjmax,'°C')}"
            color = "#F56C6C"
        elif tj > tjmax * 0.85:
            verdict = "⚠ 接近结温上限 (Tj > 85% Tj_max)"
            color = "#E6A23C"
        else:
            verdict = "✓ 散热裕量充足"
            color = "#67C23A"
        self.set_cell_value(self.r_verdict, verdict)

        # 警告区
        warns = []
        if p > 0 and need is not None and need < 0:
            warns.append(f"当前功耗 P={self.fmt(p,'W')} 过大, 即使理想散热器也无法满足 Tj_max={self.fmt(tjmax,'°C')}°C, 请降低功耗。")
        elif p > 0 and need is not None and not has_heatsink and tj > tjmax:
            warns.append(f"无散热器时结温 {self.fmt(tj,'°C')}°C 超限, 需散热器 RθSA ≤ {self.fmt(max(need,0),'°C/W')}。")
        self.set_warn("\n".join(warns) if warns else " ", "#F56C6C" if warns else "#E6A23C")
        if not warns:
            self.set_warn(" ✓ 计算完成", "#67C23A")


# =====================================================================
# Tab 3: 分压偏置驱动
# =====================================================================
class BiasDriveTab(_CalcTab):
    """分压偏置驱动: ADC 分压 (含容差误差) / LED 限流 / 三极管开关 / 上拉下拉"""

    # 上拉下拉电阻常见取值速查 (tip)
    PULLUP_TIPS = [
        "• I2C 总线上拉: 4.7kΩ (400kbps) / 2.2kΩ (1Mbps 快速模式)",
        "• 开漏输出 (中断脚): 4.7kΩ~10kΩ",
        "• 按键输入上拉: 10kΩ (去抖推荐)",
        "• LED 阳极上拉/限流: 由 VCC−VF 与 IF 决定 (见 LED 计算)",
        "• 高速信号 (SPI 片选): 1kΩ~4.7kΩ, 避免过强下拉拖慢边沿",
    ]

    def __init__(self, parent=None):
        super().__init__(parent)
        self.initUI()

    def initUI(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(16)

        main = QHBoxLayout()
        main.setSpacing(16)
        main.addWidget(self._input_card())
        main.addWidget(self._result_card(), 1)
        layout.addLayout(main)

        self.warn_label = QLabel(" ")
        self.warn_label.setWordWrap(True)
        self.warn_label.setStyleSheet(
            "color: #E6A23C; background: #FDF6EC; border: 1px solid #E6A23C;"
            "border-radius: 6px; padding: 8px 10px;"
        )
        layout.addWidget(self.warn_label)
        self.clear_warn()

        self._on_mode_changed(0)
        self.calculate()

    def _input_card(self):
        frame = QFrame()
        frame.setObjectName("card")
        frame.setFixedWidth(320)
        v = QVBoxLayout(frame)
        v.setContentsMargins(20, 20, 20, 20)
        v.setSpacing(10)
        v.addWidget(self._card_title("参数输入", "⚙️"))

        v.addWidget(QLabel("计算类型"))
        self.mode_combo = self._create_combo(
            ["ADC 分压", "LED 限流", "三极管开关"], self._on_mode_changed
        )
        v.addWidget(self.mode_combo)

        # ===== ADC 分压 =====
        self.adc_group = QWidget()
        adc_form = QFormLayout(self.adc_group)
        adc_form.setSpacing(9)
        adc_form.setLabelAlignment(Qt.AlignmentFlag.AlignRight)
        self.adc_vin = self._create_edit("3.3", self.calculate, tooltip="输入电压 (如电池/传感器输出)")
        adc_form.addRow(self._lbl("输入电压 Vin (V):"), self.adc_vin)
        self.adc_r1 = self._create_edit("100", self.calculate, tooltip="上分压电阻 (kΩ)")
        adc_form.addRow(self._lbl("上电阻 R1 (kΩ):"), self.adc_r1)
        self.adc_r2 = self._create_edit("100", self.calculate, tooltip="下分压电阻 (kΩ)")
        adc_form.addRow(self._lbl("下电阻 R2 (kΩ):"), self.adc_r2)
        self.adc_tol = self._create_edit("1", self.calculate, tooltip="电阻容差 ±% (普通 1%~5%)")
        adc_form.addRow(self._lbl("电阻容差 ±(%):"), self.adc_tol)
        self.adc_vref = self._create_edit("3.3", self.calculate, tooltip="ADC 基准电压 (用于换算 ADC 读数)")
        adc_form.addRow(self._lbl("ADC 基准 Vref (V):"), self.adc_vref)

        # ===== LED 限流 =====
        self.led_group = QWidget()
        led_form = QFormLayout(self.led_group)
        led_form.setSpacing(9)
        led_form.setLabelAlignment(Qt.AlignmentFlag.AlignRight)
        self.led_vcc = self._create_edit("5", self.calculate, tooltip="电源电压")
        led_form.addRow(self._lbl("电源 VCC (V):"), self.led_vcc)
        self.led_vf = self._create_edit("2.0", self.calculate,
                                        tooltip="LED 正向压降: 红/黄约 1.8~2.2V, 蓝/白约 3.0~3.3V")
        led_form.addRow(self._lbl("LED 压降 VF (V):"), self.led_vf)
        self.led_if = self._create_edit("10", self.calculate, tooltip="LED 工作电流 (mA), 普通指示 5~20mA")
        led_form.addRow(self._lbl("工作电流 IF (mA):"), self.led_if)

        # ===== 三极管开关 =====
        self.bjt_group = QWidget()
        bjt_form = QFormLayout(self.bjt_group)
        bjt_form.setSpacing(9)
        bjt_form.setLabelAlignment(Qt.AlignmentFlag.AlignRight)
        self.bjt_vd = self._create_edit("3.3", self.calculate, tooltip="驱动端高电平电压 (MCU 输出)")
        bjt_form.addRow(self._lbl("驱动电压 Vd (V):"), self.bjt_vd)
        self.bjt_ic = self._create_edit("100", self.calculate, tooltip="集电极负载电流 (mA)")
        bjt_form.addRow(self._lbl("集电极电流 IC (mA):"), self.bjt_ic)
        self.bjt_hfe = self._create_edit("100", self.calculate,
                                         tooltip="电流放大倍数 hFE (万用表实测更准, S8050 约 120~200)")
        bjt_form.addRow(self._lbl("放大倍数 hFE:"), self.bjt_hfe)
        self.bjt_vbe = self._create_edit("0.7", self.calculate, tooltip="基极-发射极压降, 硅管约 0.7V")
        bjt_form.addRow(self._lbl("VBE (V):"), self.bjt_vbe)
        self.bjt_k = self._create_edit("3", self.calculate,
                                       tooltip="饱和驱动系数: 开关应用取 2~5 (推荐 3)")
        bjt_form.addRow(self._lbl("饱和系数 k:"), self.bjt_k)

        self.stack = QStackedWidget()
        self.stack.addWidget(self.adc_group)
        self.stack.addWidget(self.led_group)
        self.stack.addWidget(self.bjt_group)
        v.addWidget(self.stack)

        live = QLabel("🔄 实时计算: 修改参数后结果自动更新")
        live.setFont(QFont("Microsoft YaHei", 9))
        live.setStyleSheet(
            "color: #67C23A; background: #F0F9EB; border-radius: 4px;"
            "padding: 6px 8px;"
        )
        v.addWidget(live)
        v.addStretch()
        return frame

    def _lbl(self, text):
        label = QLabel(text)
        label.setFont(QFont("Microsoft YaHei", 10))
        label.setStyleSheet("color: #6E6E73;")
        return label

    def _on_mode_changed(self, index):
        """模式切换 → 显示对应输入/结果组"""
        self.stack.setCurrentIndex(index)
        if hasattr(self, "rstack"):
            self.rstack.setCurrentIndex(index)
        self.calculate()

    def _result_card(self):
        frame = QFrame()
        frame.setObjectName("card")
        v = QVBoxLayout(frame)
        v.setContentsMargins(20, 16, 20, 16)
        v.setSpacing(10)
        v.addWidget(self._card_title("计算结果", "📊"))

        # 三组结果用 QStackedWidget 切换
        self.rstack = QStackedWidget()

        # ADC 分压结果
        adc_w = QWidget()
        adc_grid = QGridLayout(adc_w)
        adc_grid.setSpacing(10)
        adc_grid.setColumnStretch(0, 1)
        adc_grid.setColumnStretch(1, 1)
        self.r_vout = self.create_result_cell(adc_grid, 0, 0, "分压输出 Vout (V)", "#007AFF")
        self.r_vout_min = self.create_result_cell(adc_grid, 0, 1, "最小值 (最坏 ±tol)", "#E6A23C")
        self.r_vout_max = self.create_result_cell(adc_grid, 1, 0, "最大值 (最坏 +tol)", "#E6A23C")
        self.r_adc_code = self.create_result_cell(adc_grid, 1, 1, "ADC 读数", "#409EFF")
        self.rstack.addWidget(adc_w)

        # LED 限流结果
        led_w = QWidget()
        led_grid = QGridLayout(led_w)
        led_grid.setSpacing(10)
        led_grid.setColumnStretch(0, 1)
        led_grid.setColumnStretch(1, 1)
        self.r_led_r = self.create_result_cell(led_grid, 0, 0, "限流电阻 R (Ω)", "#007AFF")
        self.r_led_rstd = self.create_result_cell(led_grid, 0, 1, "标准电阻 (E24)", "#67C23A")
        self.r_led_pr = self.create_result_cell(led_grid, 1, 0, "电阻功耗 (W)", "#F56C6C")
        self.r_led_pkg = self.create_result_cell(led_grid, 1, 1, "封装建议", "#409EFF")
        self.rstack.addWidget(led_w)

        # 三极管开关结果
        bjt_w = QWidget()
        bjt_grid = QGridLayout(bjt_w)
        bjt_grid.setSpacing(10)
        bjt_grid.setColumnStretch(0, 1)
        bjt_grid.setColumnStretch(1, 1)
        self.r_ib = self.create_result_cell(bjt_grid, 0, 0, "基极电流 IB (mA)", "#007AFF")
        self.r_rb = self.create_result_cell(bjt_grid, 0, 1, "基极电阻 RB (Ω)", "#409EFF")
        self.r_rbstd = self.create_result_cell(bjt_grid, 1, 0, "标准 RB (E24)", "#67C23A")
        self.r_rbp = self.create_result_cell(bjt_grid, 1, 1, "RB 功耗 (mW)", "#E6A23C")
        self.rstack.addWidget(bjt_w)

        v.addWidget(self.rstack)

        # 上拉下拉速查 (常显)
        tip_title = QLabel("💡 上拉/下拉电阻速查")
        tip_title.setFont(QFont("Microsoft YaHei", 10, QFont.Weight.Bold))
        tip_title.setStyleSheet("color: #1D1D1F;")
        v.addWidget(tip_title)
        tip = QLabel("\n".join(self.PULLUP_TIPS))
        tip.setFont(QFont("Microsoft YaHei", 9))
        tip.setWordWrap(True)
        tip.setStyleSheet(
            "color: #6E6E73; background: #F5F7FA; border-radius: 6px;"
            "padding: 6px 10px;"
        )
        v.addWidget(tip)

        v.addWidget(self._formula_note([
            "计算公式",
            "• ADC 分压: Vout = Vin×R2/(R1+R2);  最坏误差按 R1/R2 ±tol 组合",
            "• LED 限流: R = (VCC−VF)/IF,  功率 P = IF²×R",
            "• 三极管: IB = IC/hFE×k,  RB = (Vd−VBE)/IB",
        ]))
        return frame

    def calculate(self):
        if not hasattr(self, "r_vout"):
            return
        idx = self.mode_combo.currentIndex()

        if idx == 0:  # ADC 分压
            vin = self.num(self.adc_vin.text())
            r1 = self.num(self.adc_r1.text())
            r2 = self.num(self.adc_r2.text())
            tol = self.num(self.adc_tol.text())
            vref = self.num(self.adc_vref.text())
            labels = (self.r_vout, self.r_vout_min, self.r_vout_max, self.r_adc_code)
            if None in (vin, r1, r2, tol, vref):
                self.clear_results(*labels)
                self.set_warn("请输入有效的数字!", "#F56C6C")
                return
            if r1 <= 0 or r2 <= 0:
                self.clear_results(*labels)
                self.set_warn("电阻必须大于 0!", "#F56C6C")
                return
            t = tol / 100.0
            # 最坏情况: R1 取 ±tol 与 R2 取 ∓tol 组合
            vout = vin * r2 / (r1 + r2)
            vout_min = vin * (r2 * (1 - t)) / (r1 * (1 + t) + r2 * (1 - t))
            vout_max = vin * (r2 * (1 + t)) / (r1 * (1 - t) + r2 * (1 + t))
            code = int(round(vout / vref * 4096)) if vref > 0 else None
            code_str = f"{code} / 4096" if code is not None else "--"
            self.set_cell_value(self.r_vout, self.fmt(vout, " V"))
            self.set_cell_value(self.r_vout_min, self.fmt(vout_min, " V"))
            self.set_cell_value(self.r_vout_max, self.fmt(vout_max, " V"))
            self.set_cell_value(self.r_adc_code, code_str)
            err_mv = (vout_max - vout_min) / 2 * 1000
            if err_mv > 100:
                self.set_warn(f"⚠ 分压误差达 ±{self.fmt(err_mv,' mV')}, 建议用 0.1% 电阻或软件校准", "#E6A23C")
            else:
                self.set_warn(f"分压误差约 ±{self.fmt(err_mv,' mV')}", "#67C23A")

        elif idx == 1:  # LED 限流
            vcc = self.num(self.led_vcc.text())
            vf = self.num(self.led_vf.text())
            if_ma = self.num(self.led_if.text())
            labels = (self.r_led_r, self.r_led_rstd, self.r_led_pr, self.r_led_pkg)
            if None in (vcc, vf, if_ma):
                self.clear_results(*labels)
                self.set_warn("请输入有效的数字!", "#F56C6C")
                return
            if if_ma <= 0:
                self.clear_results(*labels)
                self.set_warn("工作电流必须大于 0!", "#F56C6C")
                return
            if vf >= vcc:
                self.clear_results(*labels)
                self.set_warn("LED 压降 VF 必须小于电源 VCC!", "#F56C6C")
                return
            i = if_ma / 1000.0
            r = (vcc - vf) / i
            r_std = _nearest_std(r, [1.0, 1.1, 1.2, 1.3, 1.5, 1.6, 1.8, 2.0, 2.2,
                                     2.4, 2.7, 3.0, 3.3, 3.6, 3.9, 4.3, 4.7, 5.1,
                                     5.6, 6.2, 6.8, 7.5, 8.2, 9.1] + [10, 12, 15,
                                     18, 22, 27, 33, 39, 47, 56, 68, 82, 100,
                                     120, 150, 180, 220, 270, 330, 390, 470, 560, 680])
            p_r = i * i * r_std
            if p_r < 0.125:
                pkg = "0603 (0.1W) 可用"
            elif p_r < 0.25:
                pkg = "0805 (0.125W) 推荐"
            else:
                pkg = "1206/2512 或大功率"
            self.set_cell_value(self.r_led_r, self.fmt(r, " Ω"))
            self.set_cell_value(self.r_led_rstd, self.fmt(r_std, " Ω"))
            self.set_cell_value(self.r_led_pr, self.fmt(p_r, " W"))
            self.set_cell_value(self.r_led_pkg, pkg)
            if p_r > 0.25:
                self.set_warn(f"⚠ 电阻功耗 {self.fmt(p_r,'W')} 偏大, 建议用标准值 {self.fmt(r_std,'Ω')} 并换大封装", "#E6A23C")
            else:
                self.set_warn(f"✓ 建议使用 E24 标准电阻 {self.fmt(r_std,'Ω')}", "#67C23A")

        else:  # 三极管开关
            vd = self.num(self.bjt_vd.text())
            ic_ma = self.num(self.bjt_ic.text())
            hfe = self.num(self.bjt_hfe.text())
            vbe = self.num(self.bjt_vbe.text())
            k = self.num(self.bjt_k.text())
            labels = (self.r_ib, self.r_rb, self.r_rbstd, self.r_rbp)
            if None in (vd, ic_ma, hfe, vbe, k):
                self.clear_results(*labels)
                self.set_warn("请输入有效的数字!", "#F56C6C")
                return
            if ic_ma <= 0 or hfe <= 0 or k <= 0:
                self.clear_results(*labels)
                self.set_warn("电流、hFE、系数必须大于 0!", "#F56C6C")
                return
            if vbe >= vd:
                self.clear_results(*labels)
                self.set_warn("驱动电压 Vd 必须大于 VBE!", "#F56C6C")
                return
            ic = ic_ma / 1000.0
            ib = ic / hfe * k
            rb = (vd - vbe) / ib
            rb_std = _nearest_std(rb, [1.0, 1.5, 2.2, 3.3, 4.7, 6.8, 10, 15, 22,
                                       33, 47, 68, 100, 150, 220, 330, 470, 680,
                                       1000, 1500, 2200, 3300, 4700, 6800, 10000])
            p_rb = ib * ib * rb_std
            self.set_cell_value(self.r_ib, self.fmt(ib * 1000, " mA"))
            self.set_cell_value(self.r_rb, self.fmt(rb, " Ω"))
            self.set_cell_value(self.r_rbstd, self.fmt(rb_std, " Ω"))
            self.set_cell_value(self.r_rbp, self.fmt(p_rb * 1000, " mW"))
            self.set_warn(f"✓ IB={self.fmt(ib*1000,'mA')}, RB 建议 {self.fmt(rb_std,'Ω')} (E24)", "#67C23A")


# =====================================================================
# Tab 4: 晶振匹配电容
# =====================================================================
class CrystalTab(_CalcTab):
    """晶振匹配电容: C1=C2=2(CL−Cs), 频偏估算"""

    # 常见晶振负载电容速查 (pF)
    CL_TIPS = [
        "• 32.768kHz 实时时钟: CL 常用 6/7/12.5 pF",
        "• 8MHz 主晶振 (STM32 等): CL 常用 12.5/18/20 pF",
        "• 12MHz/16MHz (USB 等): CL 常用 12.5/20 pF",
        "• 25MHz 无源晶振 (以太网): CL 常用 18/20 pF",
    ]

    def __init__(self, parent=None):
        super().__init__(parent)
        self.initUI()

    def initUI(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(16)

        main = QHBoxLayout()
        main.setSpacing(16)
        main.addWidget(self._input_card())
        main.addWidget(self._result_card(), 1)
        layout.addLayout(main)

        self.warn_label = QLabel(" ")
        self.warn_label.setWordWrap(True)
        self.warn_label.setStyleSheet(
            "color: #E6A23C; background: #FDF6EC; border: 1px solid #E6A23C;"
            "border-radius: 6px; padding: 8px 10px;"
        )
        layout.addWidget(self.warn_label)
        self.clear_warn()
        self.calculate()

    def _input_card(self):
        frame = QFrame()
        frame.setObjectName("card")
        frame.setFixedWidth(320)
        v = QVBoxLayout(frame)
        v.setContentsMargins(20, 20, 20, 20)
        v.setSpacing(10)
        v.addWidget(self._card_title("参数输入", "⚙️"))

        form = QFormLayout()
        form.setSpacing(9)
        form.setLabelAlignment(Qt.AlignmentFlag.AlignRight)

        self.cl_edit = self._create_edit("12.5", self.calculate,
                                         tooltip="晶振规格书中给出的负载电容 CL")
        form.addRow(self._lbl("负载电容 CL (pF):"), self.cl_edit)

        self.cs_edit = self._create_edit("4", self.calculate,
                                         tooltip="PCB 杂散电容, 约 3~5 pF (走线/焊盘)")
        form.addRow(self._lbl("杂散电容 Cs (pF):"), self.cs_edit)

        self.k_edit = self._create_edit("0.5", self.calculate,
                                        tooltip="频率拉偏系数 (ppm/pF), 典型 0.2~0.5")
        form.addRow(self._lbl("拉偏系数 (ppm/pF):"), self.k_edit)

        self.f0_edit = self._create_edit("8", self.calculate, tooltip="晶振标称频率 (MHz, 用于估算频偏 ppm 对应 Hz)")
        form.addRow(self._lbl("标称频率 (MHz):"), self.f0_edit)

        v.addLayout(form)

        live = QLabel("🔄 实时计算: 修改参数后结果自动更新")
        live.setFont(QFont("Microsoft YaHei", 9))
        live.setStyleSheet(
            "color: #67C23A; background: #F0F9EB; border-radius: 4px;"
            "padding: 6px 8px;"
        )
        v.addWidget(live)
        v.addStretch()
        return frame

    def _lbl(self, text):
        label = QLabel(text)
        label.setFont(QFont("Microsoft YaHei", 10))
        label.setStyleSheet("color: #6E6E73;")
        return label

    def _result_card(self):
        frame = QFrame()
        frame.setObjectName("card")
        v = QVBoxLayout(frame)
        v.setContentsMargins(20, 16, 20, 16)
        v.setSpacing(10)
        v.addWidget(self._card_title("计算结果", "📊"))

        grid = self._result_grid(v)
        self.r_c = self.create_result_cell(grid, 0, 0, "匹配电容 C1=C2 (pF)", "#007AFF")
        self.r_cstd = self.create_result_cell(grid, 0, 1, "标准电容值", "#67C23A")
        self.r_cl_act = self.create_result_cell(grid, 1, 0, "实际等效 CL' (pF)", "#409EFF")
        self.r_ppm = self.create_result_cell(grid, 1, 1, "频率偏差 (ppm)", "#E6A23C")
        self.r_hz = self.create_result_cell(grid, 2, 0, "对应频率偏差 (Hz)", "#F56C6C")

        v.addWidget(self._formula_note([
            "计算公式",
            "• C1 = C2 = 2 × (CL − Cs)",
            "• 实际等效负载 CL' = C1/2 + Cs (取标准电容后)",
            "• 频偏估算 Δppm ≈ (CL' − CL) × 拉偏系数",
        ]))

        tip = QLabel("常见 CL 参考\n" + "\n".join(self.CL_TIPS))
        tip.setFont(QFont("Microsoft YaHei", 9))
        tip.setWordWrap(True)
        tip.setStyleSheet(
            "color: #6E6E73; background: #F5F7FA; border-radius: 6px;"
            "padding: 6px 10px;"
        )
        v.addWidget(tip)
        return frame

    def calculate(self):
        if not hasattr(self, "r_c"):
            return
        cl = self.num(self.cl_edit.text())
        cs = self.num(self.cs_edit.text())
        k = self.num(self.k_edit.text())
        f0 = self.num(self.f0_edit.text())

        labels = (self.r_c, self.r_cstd, self.r_cl_act, self.r_ppm, self.r_hz)
        if None in (cl, cs, k):
            self.clear_results(*labels)
            self.set_warn("请输入有效的数字!", "#F56C6C")
            return
        if cl <= 0 or cs < 0 or k <= 0:
            self.clear_results(*labels)
            self.set_warn("CL、Cs、拉偏系数必须有效 (Cs≥0)!", "#F56C6C")
            return
        c = 2 * (cl - cs)
        if c <= 0:
            self.clear_results(*labels)
            self.set_warn("CL 必须大于 Cs, 否则无法匹配 (Cs 太大或 CL 太小)!", "#F56C6C")
            return
        c_std = _nearest_std(c, [1.0, 1.2, 1.5, 1.8, 2.2, 2.7, 3.3, 3.9, 4.7,
                                  5.6, 6.8, 8.2, 10, 12, 15, 18, 20, 22, 27,
                                  33, 39, 47, 56, 68, 82, 100])
        cl_act = c_std / 2 + cs
        ppm = (cl_act - cl) * k
        hz = ppm / 1e6 * f0 * 1e6 if f0 and f0 > 0 else None
        self.set_cell_value(self.r_c, self.fmt(c, " pF"))
        self.set_cell_value(self.r_cstd, self.fmt(c_std, " pF"))
        self.set_cell_value(self.r_cl_act, self.fmt(cl_act, " pF"))
        self.set_cell_value(self.r_ppm, self.fmt(ppm, " ppm"))
        self.set_cell_value(self.r_hz, self.fmt(hz, " Hz") if hz is not None else "--")
        if abs(ppm) < 1:
            self.set_warn(f"✓ 标准电容 {self.fmt(c_std,'pF')} 的频偏仅 {self.fmt(ppm,'ppm')}, 满足要求", "#67C23A")
        else:
            self.set_warn(f"⚠ 标准电容 {self.fmt(c_std,'pF')} 频偏 {self.fmt(ppm,'ppm')}, 若对时基要求高请串并调整", "#E6A23C")


# =====================================================================
# Tab 5: PCB 走线计算
# =====================================================================
class PcbTraceTab(_CalcTab):
    """PCB 走线计算: IPC-2221 载流/线宽互算 + 走线电阻与压降"""

    # 铜厚选项: 厚度 mil (IPC-2221 用 mil 计)
    COPPER = {
        "0.5oz (18µm)": 0.689,
        "1oz (35µm)": 1.378,
        "2oz (70µm)": 2.756,
    }
    RHO = 1.724e-8  # 铜电阻率 Ω·m (20°C)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.initUI()

    def initUI(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(16)

        main = QHBoxLayout()
        main.setSpacing(16)
        main.addWidget(self._input_card())
        main.addWidget(self._result_card(), 1)
        layout.addLayout(main)

        self.warn_label = QLabel(" ")
        self.warn_label.setWordWrap(True)
        self.warn_label.setStyleSheet(
            "color: #E6A23C; background: #FDF6EC; border: 1px solid #E6A23C;"
            "border-radius: 6px; padding: 8px 10px;"
        )
        layout.addWidget(self.warn_label)
        self.clear_warn()
        self.calculate()

    def _input_card(self):
        frame = QFrame()
        frame.setObjectName("card")
        frame.setFixedWidth(320)
        v = QVBoxLayout(frame)
        v.setContentsMargins(20, 20, 20, 20)
        v.setSpacing(10)
        v.addWidget(self._card_title("参数输入", "⚙️"))

        v.addWidget(QLabel("计算方向"))
        self.mode_combo = self._create_combo(["电流 → 所需线宽", "线宽 → 载流能力"], self._on_mode_changed)
        v.addWidget(self.mode_combo)

        form = QFormLayout()
        form.setSpacing(9)
        form.setLabelAlignment(Qt.AlignmentFlag.AlignRight)

        self.copper_combo = self._create_combo(list(self.COPPER.keys()), self.calculate)
        form.addRow(self._lbl("铜厚:"), self.copper_combo)

        self.layer_combo = self._create_combo(["外层 (k=0.048)", "内层 (k=0.024)"], self.calculate)
        form.addRow(self._lbl("走线层:"), self.layer_combo)

        self.dt_edit = self._create_edit("10", self.calculate, tooltip="允许温升, 常规 10°C, 大电流走线取 10~20°C")
        form.addRow(self._lbl("允许温升 ΔT (°C):"), self.dt_edit)

        self.i_edit = self._create_edit("2", self.calculate, tooltip="电流 (A) → 反推所需线宽")
        form.addRow(self._lbl("电流 I (A):"), self.i_edit)

        self.w_edit = self._create_edit("1", self.calculate, tooltip="线宽 (mm) → 计算载流能力")
        form.addRow(self._lbl("线宽 W (mm):"), self.w_edit)

        self.len_edit = self._create_edit("100", self.calculate, tooltip="走线长度 (mm, 用于算电阻/压降)")
        form.addRow(self._lbl("走线长度 L (mm):"), self.len_edit)

        v.addLayout(form)

        live = QLabel("🔄 实时计算: 修改参数后结果自动更新")
        live.setFont(QFont("Microsoft YaHei", 9))
        live.setStyleSheet(
            "color: #67C23A; background: #F0F9EB; border-radius: 4px;"
            "padding: 6px 8px;"
        )
        v.addWidget(live)
        v.addStretch()
        return frame

    def _lbl(self, text):
        label = QLabel(text)
        label.setFont(QFont("Microsoft YaHei", 10))
        label.setStyleSheet("color: #6E6E73;")
        return label

    def _on_mode_changed(self, index):
        self.calculate()

    def _result_card(self):
        frame = QFrame()
        frame.setObjectName("card")
        v = QVBoxLayout(frame)
        v.setContentsMargins(20, 16, 20, 16)
        v.setSpacing(10)
        v.addWidget(self._card_title("计算结果", "📊"))

        grid = self._result_grid(v)
        self.r_i = self.create_result_cell(grid, 0, 0, "载流能力 I (A)", "#007AFF")
        self.r_w = self.create_result_cell(grid, 0, 1, "所需/给定线宽 (mm)", "#409EFF")
        self.r_area = self.create_result_cell(grid, 1, 0, "截面积 (mm²)", "#67C23A")
        self.r_res = self.create_result_cell(grid, 1, 1, "走线电阻 (mΩ)", "#E6A23C")
        self.r_drop = self.create_result_cell(grid, 2, 0, "压降 (mV)", "#F56C6C")

        v.addWidget(self._formula_note([
            "计算公式 (IPC-2221)",
            "• 载流 I = k × ΔT^0.44 × A^0.725  (A: mil²; 外层 k=0.048, 内层 k=0.024)",
            "• 线宽 mil = A / 铜厚mil,  1mm = 39.37mil,  1oz = 35µm",
            "• 电阻 R = ρ×L/(W×t),  ρ=1.724e-8 Ω·m (20°C)",
        ]))
        return frame

    def calculate(self):
        if not hasattr(self, "r_i"):
            return
        mode = self.mode_combo.currentIndex()  # 0=电流→线宽, 1=线宽→载流
        copper_mil = self.COPPER.get(self.copper_combo.currentText(), 1.378)
        k = 0.048 if self.layer_combo.currentIndex() == 0 else 0.024
        dt = self.num(self.dt_edit.text())
        i = self.num(self.i_edit.text())
        w_mm = self.num(self.w_edit.text())
        length_mm = self.num(self.len_edit.text())

        labels = (self.r_i, self.r_w, self.r_area, self.r_res, self.r_drop)
        if None in (dt, i, w_mm, length_mm):
            self.clear_results(*labels)
            self.set_warn("请输入有效的数字!", "#F56C6C")
            return
        if dt <= 0:
            self.clear_results(*labels)
            self.set_warn("温升必须大于 0!", "#F56C6C")
            return

        if mode == 0:
            if i <= 0:
                self.clear_results(*labels)
                self.set_warn("电流必须大于 0!", "#F56C6C")
                return
            area_mil2 = (i / (k * dt ** 0.44)) ** (1 / 0.725)
            w_mil = area_mil2 / copper_mil
            w_mm = w_mil * 0.0254
            i_calc = i
        else:
            if w_mm <= 0:
                self.clear_results(*labels)
                self.set_warn("线宽必须大于 0!", "#F56C6C")
                return
            w_mil = w_mm / 0.0254
            area_mil2 = w_mil * copper_mil
            i_calc = k * dt ** 0.44 * area_mil2 ** 0.725
            i = i_calc

        # 电阻与压降
        t_m = copper_mil * 25.4e-6  # 铜厚转 m (1mil=25.4µm)
        w_m = w_mm / 1000.0
        l_m = length_mm / 1000.0
        area_m2 = w_m * t_m
        res = self.RHO * l_m / area_m2 if area_m2 > 0 else None
        drop_mv = res * i_calc * 1000 if res is not None else None

        self.set_cell_value(self.r_i, self.fmt(i_calc, " A"))
        self.set_cell_value(self.r_w, self.fmt(w_mm, " mm"))
        self.set_cell_value(self.r_area, self.fmt(area_mil2 * 0.00064516, " mm²"))
        self.set_cell_value(self.r_res, self.fmt(res * 1000, " mΩ") if res else "--")
        self.set_cell_value(self.r_drop, self.fmt(drop_mv, " mV") if drop_mv is not None else "--")

        warns = []
        if w_mm < 0.1:
            warns.append("线宽过细 (<0.1mm), 注意板厂工艺能力与阻抗一致性。")
        if drop_mv is not None and drop_mv > 50:
            warns.append(f"压降 {self.fmt(drop_mv,'mV')} 偏大, 建议加宽走线或换铜厚。")
        if not warns:
            self.set_warn(" ✓ 计算完成", "#67C23A")
        else:
            self.set_warn("\n".join(warns), "#E6A23C")


# =====================================================================
# Tab 6: 电池续航估算
# =====================================================================
class BatteryTab(_CalcTab):
    """电池续航: mAh/Wh 换算 / 多模式加权平均电流 / 续航与充电时间"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.initUI()

    def initUI(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(16)

        main = QHBoxLayout()
        main.setSpacing(16)
        main.addWidget(self._input_card())
        main.addWidget(self._result_card(), 1)
        layout.addLayout(main)

        self.warn_label = QLabel(" ")
        self.warn_label.setWordWrap(True)
        self.warn_label.setStyleSheet(
            "color: #E6A23C; background: #FDF6EC; border: 1px solid #E6A23C;"
            "border-radius: 6px; padding: 8px 10px;"
        )
        layout.addWidget(self.warn_label)
        self.clear_warn()
        self.calculate()

    def _input_card(self):
        frame = QFrame()
        frame.setObjectName("card")
        frame.setFixedWidth(320)
        v = QVBoxLayout(frame)
        v.setContentsMargins(20, 20, 20, 20)
        v.setSpacing(10)
        v.addWidget(self._card_title("参数输入", "⚙️"))

        form = QFormLayout()
        form.setSpacing(9)
        form.setLabelAlignment(Qt.AlignmentFlag.AlignRight)

        self.cap_edit = self._create_edit("3000", self.calculate, tooltip="电池额定容量 mAh")
        form.addRow(self._lbl("电池容量 C (mAh):"), self.cap_edit)

        self.volt_edit = self._create_edit("3.7", self.calculate, tooltip="电池标称电压: 锂电 3.7V, 磷酸铁锂 3.2V")
        form.addRow(self._lbl("电池电压 V (V):"), self.volt_edit)

        form.addRow(self._lbl(""), self._sec_lbl("工作模式加权 (活跃+休眠=100%)"))

        self.ia_edit = self._create_edit("150", self.calculate, tooltip="活跃/唤醒状态平均电流")
        form.addRow(self._lbl("活跃电流 (mA):"), self.ia_edit)

        self.pa_edit = self._create_edit("50", self.calculate, tooltip="活跃时间占比 %")
        form.addRow(self._lbl("活跃占比 (%):"), self.pa_edit)

        self.is_edit = self._create_edit("0.5", self.calculate, tooltip="休眠/睡眠状态平均电流")
        form.addRow(self._lbl("休眠电流 (mA):"), self.is_edit)

        self.ps_edit = self._create_edit("50", self.calculate, tooltip="休眠时间占比 %")
        form.addRow(self._lbl("休眠占比 (%):"), self.ps_edit)

        form.addRow(self._lbl(""), self._sec_lbl("充电"))

        self.chg_edit = self._create_edit("1000", self.calculate, tooltip="充电电流 mA")
        form.addRow(self._lbl("充电电流 (mA):"), self.chg_edit)

        self.eta_edit = self._create_edit("85", self.calculate, tooltip="充电效率 %, 锂电池约 80~90%")
        form.addRow(self._lbl("充电效率 (%):"), self.eta_edit)

        v.addLayout(form)

        live = QLabel("🔄 实时计算: 修改参数后结果自动更新")
        live.setFont(QFont("Microsoft YaHei", 9))
        live.setStyleSheet(
            "color: #67C23A; background: #F0F9EB; border-radius: 4px;"
            "padding: 6px 8px;"
        )
        v.addWidget(live)
        v.addStretch()
        return frame

    def _lbl(self, text):
        label = QLabel(text)
        label.setFont(QFont("Microsoft YaHei", 10))
        label.setStyleSheet("color: #6E6E73;")
        return label

    def _sec_lbl(self, text):
        label = QLabel(f"▎ {text}")
        label.setFont(QFont("Microsoft YaHei", 10, QFont.Weight.Bold))
        label.setStyleSheet("color: #007AFF;")
        return label

    def _result_card(self):
        frame = QFrame()
        frame.setObjectName("card")
        v = QVBoxLayout(frame)
        v.setContentsMargins(20, 16, 20, 16)
        v.setSpacing(10)
        v.addWidget(self._card_title("计算结果", "📊"))

        grid = self._result_grid(v)
        self.r_wh = self.create_result_cell(grid, 0, 0, "电池能量 (Wh)", "#007AFF")
        self.r_avg = self.create_result_cell(grid, 0, 1, "平均电流 (mA)", "#409EFF")
        self.r_hours = self.create_result_cell(grid, 1, 0, "续航时间", "#67C23A")
        self.r_days = self.create_result_cell(grid, 1, 1, "折合天数", "#E6A23C")
        self.r_chg = self.create_result_cell(grid, 2, 0, "充电时间", "#F56C6C")

        v.addWidget(self._formula_note([
            "计算公式",
            "• 能量 Wh = mAh × V / 1000",
            "• 平均电流 = Σ(模式电流 × 占比)",
            "• 续航 h = 容量 mAh / 平均电流 mA",
            "• 充电 h = 容量 / 充电电流 / 效率",
        ]))
        return frame

    def calculate(self):
        if not hasattr(self, "r_wh"):
            return
        cap = self.num(self.cap_edit.text())
        volt = self.num(self.volt_edit.text())
        ia = self.num(self.ia_edit.text())
        pa = self.num(self.pa_edit.text())
        isl = self.num(self.is_edit.text())
        ps = self.num(self.ps_edit.text())
        chg = self.num(self.chg_edit.text())
        eta = self.num(self.eta_edit.text())

        labels = (self.r_wh, self.r_avg, self.r_hours, self.r_days, self.r_chg)
        if None in (cap, volt, ia, pa, isl, ps, chg, eta):
            self.clear_results(*labels)
            self.set_warn("请输入有效的数字!", "#F56C6C")
            return
        if cap <= 0 or volt <= 0 or ia < 0 or isl < 0 or chg <= 0 or eta <= 0:
            self.clear_results(*labels)
            self.set_warn("容量、电压、充电电流、效率必须大于 0!", "#F56C6C")
            return
        if abs(pa + ps - 100) > 0.5:
            self.clear_results(*labels)
            self.set_warn("活跃+休眠占比应等于 100%!", "#E6A23C")
            return

        wh = cap * volt / 1000.0
        avg_ma = (ia * pa + isl * ps) / 100.0
        hours = cap / avg_ma if avg_ma > 0 else None
        days = hours / 24.0 if hours is not None else None
        chg_h = cap / chg / (eta / 100.0)

        # 续航时间格式化: <1h 显示分钟, >48h 显示天
        if hours is None:
            h_str = "--"
        elif hours < 1:
            h_str = self.fmt(hours * 60, " 分钟")
        elif hours >= 48:
            h_str = self.fmt(hours / 24, " 天")
        else:
            h_str = self.fmt(hours, " 小时")
        d_str = self.fmt(days, " 天") if days is not None else "--"

        self.set_cell_value(self.r_wh, self.fmt(wh, " Wh"))
        self.set_cell_value(self.r_avg, self.fmt(avg_ma, " mA"))
        self.set_cell_value(self.r_hours, h_str)
        self.set_cell_value(self.r_days, d_str)
        self.set_cell_value(self.r_chg, self.fmt(chg_h, " 小时"))

        if hours is not None and hours < 12:
            self.set_warn(f"⚠ 续航仅 {self.fmt(hours,' 小时')}, 建议降低活跃电流或增大电池容量", "#E6A23C")
        else:
            self.set_warn(" ✓ 计算完成", "#67C23A")


# =====================================================================
# Tab 7: 波特率/定时器计算
# =====================================================================
class BaudTimerTab(_CalcTab):
    """波特率/定时器: 8051 串口波特率 / MCU 定时器周期 / PWM 频率占空比"""

    # 常用 MCU 预设 (config.json hardware_toolbox.mcu_presets 可覆盖)
    DEFAULT_PRESETS = {
        "8051 @ 11.0592MHz (经典)": 11.0592,
        "8051 @ 12MHz":              12.0,
        "STM32F1 @ 72MHz":           72.0,
        "STM32F4 @ 168MHz":          168.0,
        "GD32 @ 108MHz":             108.0,
        "ESP32 @ 240MHz":            240.0,
    }

    def __init__(self, parent=None):
        super().__init__(parent)
        self.presets = self._load_lib("mcu_presets", self.DEFAULT_PRESETS)
        self.initUI()

    def initUI(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(16)

        main = QHBoxLayout()
        main.setSpacing(16)
        main.addWidget(self._input_card())
        main.addWidget(self._result_card(), 1)
        layout.addLayout(main)

        self.warn_label = QLabel(" ")
        self.warn_label.setWordWrap(True)
        self.warn_label.setStyleSheet(
            "color: #E6A23C; background: #FDF6EC; border: 1px solid #E6A23C;"
            "border-radius: 6px; padding: 8px 10px;"
        )
        layout.addWidget(self.warn_label)
        self.clear_warn()
        self._on_mode_changed(0)
        self.calculate()

    def _input_card(self):
        frame = QFrame()
        frame.setObjectName("card")
        frame.setFixedWidth(320)
        v = QVBoxLayout(frame)
        v.setContentsMargins(20, 20, 20, 20)
        v.setSpacing(10)
        v.addWidget(self._card_title("参数输入", "⚙️"))

        v.addWidget(QLabel("计算类型"))
        self.mode_combo = self._create_combo(
            ["8051 串口波特率", "定时器周期", "PWM 频率/占空比"], self._on_mode_changed
        )
        v.addWidget(self.mode_combo)

        v.addWidget(QLabel("MCU 预设 (自动填充主频)"))
        self.preset_combo = self._create_combo(
            list(self.presets.keys()), self._on_preset_changed,
            tooltip="选择常用 MCU 自动填充系统主频"
        )
        v.addWidget(self.preset_combo)

        # ===== 8051 波特率 =====
        self.bd_group = QWidget()
        bd_form = QFormLayout(self.bd_group)
        bd_form.setSpacing(9)
        bd_form.setLabelAlignment(Qt.AlignmentFlag.AlignRight)
        self.bd_fosc = self._create_edit("11.0592", self.calculate, tooltip="晶振频率 MHz")
        bd_form.addRow(self._lbl("晶振 Fosc (MHz):"), self.bd_fosc)
        self.bd_baud = self._create_edit("9600", self.calculate, tooltip="目标波特率 bps")
        bd_form.addRow(self._lbl("目标波特率 (bps):"), self.bd_baud)
        self.bd_smod = self._create_combo(["SMOD=0 (普通)", "SMOD=1 (倍速)"], self.calculate)
        bd_form.addRow(self._lbl("波特率倍增:"), self.bd_smod)

        # ===== 定时器 =====
        self.tm_group = QWidget()
        tm_form = QFormLayout(self.tm_group)
        tm_form.setSpacing(9)
        tm_form.setLabelAlignment(Qt.AlignmentFlag.AlignRight)
        self.tm_fsys = self._create_edit("12", self.calculate, tooltip="系统主频 MHz")
        tm_form.addRow(self._lbl("主频 Fsys (MHz):"), self.tm_fsys)
        self.tm_psc = self._create_edit("12", self.calculate, tooltip="预分频 (8051 常用 12; STM32 为 PSC+1)")
        tm_form.addRow(self._lbl("预分频:"), self.tm_psc)
        self.tm_load = self._create_edit("65536", self.calculate, tooltip="重装值 (16 位定时器 0~65535; 8051 重装 = 65536−计数)")
        tm_form.addRow(self._lbl("重装值:"), self.tm_load)

        # ===== PWM =====
        self.pwm_group = QWidget()
        pwm_form = QFormLayout(self.pwm_group)
        pwm_form.setSpacing(9)
        pwm_form.setLabelAlignment(Qt.AlignmentFlag.AlignRight)
        self.pwm_fsys = self._create_edit("72", self.calculate, tooltip="系统主频 MHz")
        pwm_form.addRow(self._lbl("主频 Fsys (MHz):"), self.pwm_fsys)
        self.pwm_psc = self._create_edit("71", self.calculate, tooltip="预分频 PSC (频率 = Fsys/(PSC+1)/(ARR+1))")
        pwm_form.addRow(self._lbl("预分频 PSC:"), self.pwm_psc)
        self.pwm_arr = self._create_edit("999", self.calculate, tooltip="自动重装 ARR (决定周期)")
        pwm_form.addRow(self._lbl("自动重装 ARR:"), self.pwm_arr)
        self.pwm_ccr = self._create_edit("500", self.calculate, tooltip="比较值 CCR (决定占空比)")
        pwm_form.addRow(self._lbl("比较值 CCR:"), self.pwm_ccr)

        self.stack = QStackedWidget()
        self.stack.addWidget(self.bd_group)
        self.stack.addWidget(self.tm_group)
        self.stack.addWidget(self.pwm_group)
        v.addWidget(self.stack)

        live = QLabel("🔄 实时计算: 修改参数后结果自动更新")
        live.setFont(QFont("Microsoft YaHei", 9))
        live.setStyleSheet(
            "color: #67C23A; background: #F0F9EB; border-radius: 4px;"
            "padding: 6px 8px;"
        )
        v.addWidget(live)
        v.addStretch()

        self._on_preset_changed(0)
        return frame

    def _lbl(self, text):
        label = QLabel(text)
        label.setFont(QFont("Microsoft YaHei", 10))
        label.setStyleSheet("color: #6E6E73;")
        return label

    def _on_preset_changed(self, index):
        """MCU 预设切换 → 填充各模式主频"""
        name = self.preset_combo.currentText()
        f = self.presets.get(name)
        if f is None:
            return
        fs = str(f)
        self.bd_fosc.setText(fs)
        self.tm_fsys.setText(fs)
        self.pwm_fsys.setText(fs)

    def _on_mode_changed(self, index):
        self.stack.setCurrentIndex(index)
        if hasattr(self, "rstack"):
            self.rstack.setCurrentIndex(index)
        self.calculate()

    def _result_card(self):
        frame = QFrame()
        frame.setObjectName("card")
        v = QVBoxLayout(frame)
        v.setContentsMargins(20, 16, 20, 16)
        v.setSpacing(10)
        v.addWidget(self._card_title("计算结果", "📊"))

        self.rstack = QStackedWidget()

        # 8051 波特率
        bd_w = QWidget()
        bd_grid = QGridLayout(bd_w)
        bd_grid.setSpacing(10)
        bd_grid.setColumnStretch(0, 1)
        bd_grid.setColumnStretch(1, 1)
        self.r_th1 = self.create_result_cell(bd_grid, 0, 0, "TH1 重装值", "#007AFF")
        self.r_baud_act = self.create_result_cell(bd_grid, 0, 1, "实际波特率 (bps)", "#409EFF")
        self.r_baud_err = self.create_result_cell(bd_grid, 1, 0, "波特率误差 (%)", "#F56C6C")
        self.r_baud_ok = self.create_result_cell(bd_grid, 1, 1, "是否可用", "#67C23A")
        self.rstack.addWidget(bd_w)

        # 定时器
        tm_w = QWidget()
        tm_grid = QGridLayout(tm_w)
        tm_grid.setSpacing(10)
        tm_grid.setColumnStretch(0, 1)
        tm_grid.setColumnStretch(1, 1)
        self.r_tm = self.create_result_cell(tm_grid, 0, 0, "定时周期", "#007AFF")
        self.r_tm_freq = self.create_result_cell(tm_grid, 0, 1, "对应频率 (Hz)", "#409EFF")
        self.r_tm_max = self.create_result_cell(tm_grid, 1, 0, "最大定时 (65535 满值)", "#67C23A")
        self.rstack.addWidget(tm_w)

        # PWM
        pwm_w = QWidget()
        pwm_grid = QGridLayout(pwm_w)
        pwm_grid.setSpacing(10)
        pwm_grid.setColumnStretch(0, 1)
        pwm_grid.setColumnStretch(1, 1)
        self.r_freq = self.create_result_cell(pwm_grid, 0, 0, "PWM 频率", "#007AFF")
        self.r_duty = self.create_result_cell(pwm_grid, 0, 1, "占空比 (%)", "#409EFF")
        self.r_pwm_res = self.create_result_cell(pwm_grid, 1, 0, "分辨率 (bits)", "#67C23A")
        self.rstack.addWidget(pwm_w)

        v.addWidget(self.rstack)

        v.addWidget(self._formula_note([
            "计算公式",
            "• 8051 (Timer1 模式2):  Baud = Fosc×2^SMOD / (32×(256−TH1))",
            "• 定时器:  t = (65536−重装值) × 预分频 / Fsys  (16 位模式1)",
            "• PWM:  f = Fsys / (PSC+1) / (ARR+1),  占空比 = CCR / (ARR+1)",
        ]))
        return frame

    def calculate(self):
        if not hasattr(self, "r_th1"):
            return
        idx = self.mode_combo.currentIndex()

        if idx == 0:  # 8051 波特率
            fosc = self.num(self.bd_fosc.text())
            baud = self.num(self.bd_baud.text())
            smod = 1 if self.bd_smod.currentIndex() == 1 else 0
            labels = (self.r_th1, self.r_baud_act, self.r_baud_err, self.r_baud_ok)
            if None in (fosc, baud):
                self.clear_results(*labels)
                self.set_warn("请输入有效的数字!", "#F56C6C")
                return
            if fosc <= 0 or baud <= 0:
                self.clear_results(*labels)
                self.set_warn("晶振频率与波特率必须大于 0!", "#F56C6C")
                return
            th1 = 256 - (fosc * 1e6 * (2 ** smod)) / (32.0 * baud)
            th1_int = int(round(th1))
            if not (0 <= th1_int <= 255):
                self.clear_results(*labels)
                self.set_warn("重装值超出 8 位范围 (0~255), 请检查晶振/波特率组合!", "#F56C6C")
                return
            baud_act = (fosc * 1e6 * (2 ** smod)) / (32.0 * (256 - th1_int))
            err = (baud_act - baud) / baud * 100
            ok = "✓ 可用" if abs(err) <= 2.0 else "✗ 误差过大"
            self.set_cell_value(self.r_th1, f"TH1 = {self.fmt(th1, '', 4)}\n(取整 {th1_int})")
            self.set_cell_value(self.r_baud_act, self.fmt(baud_act, "", 6))
            self.set_cell_value(self.r_baud_err, self.fmt(err, " %"))
            self.set_cell_value(self.r_baud_ok, ok)
            if abs(err) > 2.0:
                self.set_warn(
                    f"⚠ 波特率误差 {self.fmt(err,'%')} 过大 (>2%)!\n"
                    "建议改用 11.0592MHz 晶振 (可精确分频出常用波特率)。",
                    "#F56C6C"
                )
            else:
                self.set_warn(f"✓ 推荐用 11.0592MHz 晶振时此组合误差可忽略", "#67C23A")

        elif idx == 1:  # 定时器
            fsys = self.num(self.tm_fsys.text())
            psc = self.num(self.tm_psc.text())
            load = self.num(self.tm_load.text())
            labels = (self.r_tm, self.r_tm_freq, self.r_tm_max)
            if None in (fsys, psc, load):
                self.clear_results(*labels)
                self.set_warn("请输入有效的数字!", "#F56C6C")
                return
            if fsys <= 0 or psc <= 0:
                self.clear_results(*labels)
                self.set_warn("主频与预分频必须大于 0!", "#F56C6C")
                return
            t = (65536 - load) * psc / (fsys * 1e6)
            if t <= 0:
                self.clear_results(*labels)
                self.set_warn("重装值需小于 65536 才能产生定时!", "#F56C6C")
                return
            t_max = 65535 * psc / (fsys * 1e6)
            # 格式化
            if t < 1e-3:
                t_str = self.fmt(t * 1e6, " µs")
            elif t < 1:
                t_str = self.fmt(t * 1e3, " ms")
            else:
                t_str = self.fmt(t, " s")
            tmax_str = self.fmt(t_max * 1e3, " ms") if t_max < 1 else self.fmt(t_max, " s")
            self.set_cell_value(self.r_tm, t_str)
            self.set_cell_value(self.r_tm_freq, self.fmt(1 / t, " Hz"))
            self.set_cell_value(self.r_tm_max, tmax_str)
            self.set_warn(" ✓ 计算完成", "#67C23A")

        else:  # PWM
            fsys = self.num(self.pwm_fsys.text())
            psc = self.num(self.pwm_psc.text())
            arr = self.num(self.pwm_arr.text())
            ccr = self.num(self.pwm_ccr.text())
            labels = (self.r_freq, self.r_duty, self.r_pwm_res)
            if None in (fsys, psc, arr, ccr):
                self.clear_results(*labels)
                self.set_warn("请输入有效的数字!", "#F56C6C")
                return
            if fsys <= 0 or psc < 0 or arr < 0:
                self.clear_results(*labels)
                self.set_warn("主频、PSC、ARR 必须有效 (PSC/ARR ≥ 0)!", "#F56C6C")
                return
            f = fsys * 1e6 / ((psc + 1) * (arr + 1))
            duty = ccr / (arr + 1) * 100
            bits = int(math.log2(arr + 1)) if arr + 1 > 1 else 0
            self.set_cell_value(self.r_freq, self.fmt(f, " Hz"))
            self.set_cell_value(self.r_duty, self.fmt(duty, " %"))
            self.set_cell_value(self.r_pwm_res, f"{bits} bits (ARR+1={int(arr+1)})")
            if not (0 <= ccr <= arr):
                self.set_warn("CCR 超出 0~ARR 范围, 占空比将钳位!", "#E6A23C")
            else:
                self.set_warn(" ✓ 计算完成", "#67C23A")


# =====================================================================
# 硬件工具箱主页面 (Tab 聚合)
# =====================================================================
class HardwareToolboxPage(QWidget):
    """硬件工具箱: 7 个硬件工程师计算工具 (Tab 聚合页)"""

    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(16)

        title = QLabel("🔧 硬件工具箱")
        title.setFont(QFont("Microsoft YaHei", 20, QFont.Weight.Bold))
        title.setStyleSheet("color: #1D1D1F;")
        layout.addWidget(title)

        subtitle = QLabel("硬件工程师常用计算: 电源 / 散热 / 偏置驱动 / 晶振 / PCB / 电池 / 波特率")
        subtitle.setFont(QFont("Microsoft YaHei", 10))
        subtitle.setStyleSheet("color: #6E6E73;")
        layout.addWidget(subtitle)

        # Tab 内容放入滚动容器: 避免页面内容高度把窗口最小尺寸撑大 (窗口无法缩小),
        # 内容超高时出现滚动条, 窗口可自由缩放
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setStyleSheet("QScrollArea { background: transparent; border: none; }")
        layout.addWidget(scroll, 1)

        inner = QWidget()
        inner.setStyleSheet("background: transparent;")
        inner_layout = QVBoxLayout(inner)
        inner_layout.setContentsMargins(0, 0, 0, 0)
        inner_layout.setSpacing(16)

        tabs = QTabWidget()
        tabs.setStyleSheet(_TAB_QSS)
        tabs.addTab(DcdcBuckTab(), "⚡ DC-DC BUCK")
        # 复用功率变换页 (LDO 降压 / 电阻选型 / AI 分析) 并入工具箱 Tab
        from app.pages.power_conversion_page import PowerConversionPage
        tabs.addTab(PowerConversionPage(), "🔌 LDO 降压")
        tabs.addTab(ThermalTab(), "🌡 散热功耗")
        tabs.addTab(BiasDriveTab(), "🔗 分压偏置")
        tabs.addTab(CrystalTab(), "💎 晶振匹配")
        tabs.addTab(PcbTraceTab(), "🖥 PCB 走线")
        tabs.addTab(BatteryTab(), "🔋 电池续航")
        tabs.addTab(BaudTimerTab(), "⏱ 波特率定时")
        inner_layout.addWidget(tabs, 1)
        scroll.setWidget(inner)

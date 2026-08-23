"""
常识速查合集页 (原"常识查询"栏目升级)

包含 6 个速查 Tab (全部离线本地数据):
1. 色环电阻: 直接复用 ResistorColorCodePage (不重写)
2. 单位换算: dBm/mW/V 射频功率互算 / 频率↔周期↔波长 / 电容、电阻单位联动
3. E 系列标称值: E6/E12/E24/E48/E96 标准电阻值表 (一键复制)
4. 接口引脚速查: UART/RS232/RS485/I2C/SPI/USB/JTAG/SWD/CAN/RJ45
5. 贴片封装尺寸: SOT/SOP/SSOP/TSSOP/QFN/LQFP/BGA 常见焊盘尺寸
6. AWG 线规表: 30~16AWG 线径/截面积/载流/电阻 (公式生成)

速查表均支持 QTableWidget 选中复制 + "复制全部"按钮。
"""

import math
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit, QFormLayout,
    QTableWidget, QTableWidgetItem, QAbstractItemView, QHeaderView,
    QPushButton, QComboBox, QTabWidget, QGridLayout, QFrame,
    QScrollArea,
)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QFont

from app.core.theme import system_font, TEXT, TEXT_SECONDARY, ACCENT

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


class _LookupTab(QWidget):
    """速查 Tab 共用基类: 只读表格 + 复制能力"""

    @staticmethod
    def _table():
        """创建斑马纹只读表格"""
        table = QTableWidget()
        table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        table.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        table.setAlternatingRowColors(True)
        table.setStyleSheet("""
            QTableWidget {
                background: #FFFFFF; border: 1px solid #E5E5EA;
                border-radius: 6px; gridline-color: #F0F0F2;
                font-family: "Microsoft YaHei"; font-size: 10pt; color: #1D1D1F;
            }
            QTableWidget::item { padding: 4px 8px; }
            QHeaderView::section {
                background: #F7F8FA; border: none; border-bottom: 1px solid #E5E5EA;
                padding: 6px 8px; font-family: "Microsoft YaHei";
                font-size: 10pt; font-weight: bold; color: #6E6E73;
            }
        """)
        return table

    def _fill(self, table, headers, rows):
        """填充表格数据"""
        table.setColumnCount(len(headers))
        table.setHorizontalHeaderLabels(headers)
        table.setRowCount(len(rows))
        for r, row in enumerate(rows):
            for c, val in enumerate(row):
                item = QTableWidgetItem(str(val))
                if c == 0:
                    item.setFont(QFont("Microsoft YaHei", 10, QFont.Weight.Bold))
                table.setItem(r, c, item)
        table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        table.verticalHeader().setVisible(False)

    def _copy_btn(self, table, title="复制全部"):
        """复制按钮: 将表格内容转为制表符文本写入剪贴板"""
        btn = QPushButton(f"📋 {title}")
        btn.setCursor(Qt.CursorShape.PointingHandCursor)
        btn.setStyleSheet(
            f"QPushButton {{ background: {ACCENT}; color: white; border: none;"
            "border-radius: 6px; padding: 6px 16px; font-weight: bold; }"
            f"QPushButton:hover {{ background: #3395FF; }}"
        )

        def _copy():
            rows = table.rowCount()
            cols = table.columnCount()
            lines = []
            lines.append("\t".join(table.horizontalHeaderItem(c).text()
                                   for c in range(cols)))
            for r in range(rows):
                lines.append("\t".join(table.item(r, c).text() if table.item(r, c) else ""
                                     for c in range(cols)))
            from PyQt6.QtWidgets import QApplication
            QApplication.clipboard().setText("\n".join(lines))
            btn.setText("✓ 已复制")
            from PyQt6.QtCore import QTimer
            QTimer.singleShot(1500, lambda: btn.setText(f"📋 {title}"))

        btn.clicked.connect(_copy)
        return btn


# =====================================================================
# Tab 2: 单位换算
# =====================================================================
class _UnitConvertTab(_LookupTab):
    """单位换算: 射频功率 / 频率周期波长 / 电容电阻单位联动 (双向实时)"""

    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(16)
        self._edits = {}  # (group, key) -> QLineEdit

        # ---- 射频功率卡片 ----
        layout.addWidget(self._card_title("射频功率 (50Ω 系统, 双向换算)", "📡"))
        rf = QGridLayout()
        rf.setSpacing(10)
        self._mk_edit("rf", "dBm", "0", rf, 0, 0)
        self._mk_edit("rf", "mW", "1", rf, 0, 1)
        self._mk_edit("rf", "Vrms", "0.2236", rf, 0, 2)
        layout.addLayout(rf)

        # ---- 频率 / 周期 / 波长 ----
        layout.addWidget(self._card_title("频率 ↔ 周期 ↔ 波长 (双向换算)", "🌊"))
        fw = QGridLayout()
        fw.setSpacing(10)
        self._mk_edit("freq", "频率 f (MHz)", "100", fw, 0, 0)
        self._mk_edit("freq", "周期 T (µs)", "10", fw, 0, 1)
        self._mk_edit("freq", "波长 λ (m)", "2.998", fw, 0, 2)
        layout.addLayout(fw)

        # ---- 电容 / 电阻单位 ----
        layout.addWidget(self._card_title("电容 / 电阻单位联动换算", "⚡"))
        cr = QGridLayout()
        cr.setSpacing(10)
        self._mk_edit("cap", "µF", "0.1", cr, 0, 0)
        self._mk_edit("cap", "nF", "100", cr, 0, 1)
        self._mk_edit("cap", "pF", "100000", cr, 0, 2)
        self._mk_edit("res", "Ω", "4700", cr, 1, 0)
        self._mk_edit("res", "kΩ", "4.7", cr, 1, 1)
        self._mk_edit("res", "MΩ", "0.0047", cr, 1, 2)
        layout.addLayout(cr)

        note = QLabel(
            "💡 dBm/mW/V 按 50Ω 系统:  dBm = 10·lg(mW);  V = √(mW×0.05)\n"
            "💡 波长 λ = c/f (c ≈ 2.998×10⁸ m/s);  T = 1/f\n"
            "💡 电容: 1µF = 1000nF = 1000000pF;  电阻: 1MΩ = 1000kΩ = 10⁶Ω"
        )
        note.setFont(system_font(9))
        note.setStyleSheet(
            "color: #6E6E73; background: #F5F7FA; border-radius: 6px;"
            "padding: 8px 12px;"
        )
        layout.addWidget(note)
        layout.addStretch()

        for key in ("rf", "freq", "cap", "res"):
            self._recalc(key)

    def _card_title(self, text, icon):
        bar = QFrame()
        bar.setFixedSize(4, 20)
        bar.setStyleSheet("background: #007AFF; border-radius: 2px;")
        label = QLabel(f"{icon}  {text}")
        label.setFont(system_font(12, weight=QFont.Weight.Bold))
        label.setStyleSheet(f"color: {TEXT};")
        h = QHBoxLayout()
        h.setSpacing(8)
        h.addWidget(bar)
        h.addWidget(label)
        h.addStretch()
        wrap = QWidget()
        wrap.setLayout(h)
        return wrap

    def _mk_edit(self, group, label_text, default, grid, row, col):
        """创建联动输入框 (标签在上方, 输入框在下)"""
        box = QWidget()
        v = QVBoxLayout(box)
        v.setContentsMargins(0, 0, 0, 0)
        v.setSpacing(4)
        lab = QLabel(label_text)
        lab.setFont(system_font(9))
        lab.setStyleSheet(f"color: {TEXT_SECONDARY};")
        v.addWidget(lab)
        edit = QLineEdit(default)
        edit.setMinimumHeight(36)
        edit.setAlignment(Qt.AlignmentFlag.AlignRight)
        edit.setStyleSheet("""
            QLineEdit { background: #FFFFFF; border: 1px solid #DCDFE6;
                border-radius: 6px; padding: 4px 10px;
                font-family: "Microsoft YaHei"; font-size: 10pt; color: #303133; }
            QLineEdit:focus { border: 1px solid #007AFF; }
        """)
        edit.textChanged.connect(lambda *_, k=label_text: self._recalc(group, k))
        v.addWidget(edit)
        grid.addWidget(box, row, col)
        self._edits[(group, label_text)] = edit

    @staticmethod
    def _num(text):
        try:
            return float(str(text).strip())
        except (ValueError, AttributeError):
            return None

    def _set(self, group, key, value):
        edit = self._edits.get((group, key))
        if edit is None or value is None:
            return
        s = f"{value:.6g}"
        # 仅当为小数/科学计数时才去尾 0, 避免 "10" → "1"、"4700" → "47"
        if "." in s or "e" in s:
            s = s.rstrip("0").rstrip(".")
        edit.blockSignals(True)
        edit.setText(s)
        edit.blockSignals(False)

    def _recalc(self, group, source_key=None):
        """按最近修改的输入值更新同组其他输入框 (来源由 textChanged 传入, 防递归)"""
        edits = {k: v for k, v in self._edits.items() if k[0] == group}
        src_key, src_val = None, None
        if source_key is not None:
            edit = self._edits.get((group, source_key))
            v = self._num(edit.text()) if edit else None
            if v is not None:
                src_key, src_val = source_key, v
        # 初始调用 (无来源): 取第一个非空输入
        if src_key is None:
            for (g, key), edit in edits.items():
                v = self._num(edit.text())
                if v is not None:
                    src_key, src_val = key, v
                    break

        if src_key is None:
            return

        if group == "rf":
            if src_key == "dBm":
                mw = 10 ** (src_val / 10)
                v = math.sqrt(mw * 0.05)
                self._set(group, "mW", mw)
                self._set(group, "Vrms", v)
            elif src_key == "mW":
                self._set(group, "dBm", 10 * math.log10(src_val))
                self._set(group, "Vrms", math.sqrt(src_val * 0.05))
            else:  # Vrms
                mw = (src_val * src_val) / 0.05
                self._set(group, "dBm", 10 * math.log10(mw))
                self._set(group, "mW", mw)
        elif group == "freq":
            if src_key.startswith("频率"):
                t = 1.0 / (src_val * 1e6) * 1e6  # MHz → 周期 µs
                lam = 2.99792458e8 / (src_val * 1e6)
                self._set(group, "周期 T (µs)", t)
                self._set(group, "波长 λ (m)", lam)
            elif src_key.startswith("周期"):
                f_mhz = 1.0 / (src_val * 1e-6) / 1e6
                lam = 2.99792458e8 * src_val * 1e-6
                self._set(group, "频率 f (MHz)", f_mhz)
                self._set(group, "波长 λ (m)", lam)
            else:  # 波长
                f_mhz = 2.99792458e8 / src_val / 1e6
                t = 1.0 / (f_mhz * 1e6) * 1e6
                self._set(group, "频率 f (MHz)", f_mhz)
                self._set(group, "周期 T (µs)", t)
        elif group == "cap":
            if src_key == "µF":
                self._set(group, "nF", src_val * 1000)
                self._set(group, "pF", src_val * 1e6)
            elif src_key == "nF":
                self._set(group, "µF", src_val / 1000)
                self._set(group, "pF", src_val * 1000)
            else:  # pF
                self._set(group, "µF", src_val / 1e6)
                self._set(group, "nF", src_val / 1000)
        elif group == "res":
            if src_key == "Ω":
                self._set(group, "kΩ", src_val / 1000)
                self._set(group, "MΩ", src_val / 1e6)
            elif src_key == "kΩ":
                self._set(group, "Ω", src_val * 1000)
                self._set(group, "MΩ", src_val / 1000)
            else:  # MΩ
                self._set(group, "Ω", src_val * 1e6)
                self._set(group, "kΩ", src_val * 1000)


# =====================================================================
# Tab 3: E 系列标称值
# =====================================================================
class _ESeriesTab(_LookupTab):
    """E 系列标准电阻值表 (E6/E12/E24/E48/E96)"""

    # 各系列标准值 (1~10 基准, 实际 ×10^n)
    SERIES = {
        "E6":  [10, 15, 22, 33, 47, 68],
        "E12": [10, 12, 15, 18, 22, 27, 33, 39, 47, 56, 68, 82],
        "E24": [10, 11, 12, 13, 15, 16, 18, 20, 22, 24, 27, 30, 33, 36, 39,
                43, 47, 51, 56, 62, 68, 75, 82, 91],
        "E48": [10.0, 10.5, 11.0, 11.5, 12.1, 12.7, 13.3, 14.0, 14.7, 15.4,
                16.2, 16.9, 17.8, 18.7, 19.6, 20.5, 21.5, 22.6, 23.7, 24.9,
                26.1, 27.4, 28.7, 30.1, 31.6, 33.2, 34.8, 36.5, 38.3, 40.2,
                42.2, 44.2, 46.4, 48.7, 51.1, 53.6, 56.2, 59.0, 61.9, 64.9,
                68.1, 71.5, 75.0, 78.7, 82.5, 86.6, 90.9, 95.3],
        "E96": [10.0, 10.2, 10.5, 10.7, 11.0, 11.3, 11.5, 11.8, 12.1, 12.4,
                12.7, 13.0, 13.3, 13.7, 14.0, 14.3, 14.7, 15.0, 15.4, 15.8,
                16.2, 16.5, 16.9, 17.4, 17.8, 18.2, 18.7, 19.1, 19.6, 20.0,
                20.5, 21.0, 21.5, 22.1, 22.6, 23.2, 23.7, 24.3, 24.9, 25.5,
                26.1, 26.7, 27.4, 28.0, 28.7, 29.4, 30.1, 30.9, 31.6, 32.4,
                33.2, 34.0, 34.8, 35.7, 36.5, 37.4, 38.3, 39.2, 40.2, 41.2,
                42.2, 43.2, 44.2, 45.3, 46.4, 47.5, 48.7, 49.9, 51.1, 52.3,
                53.6, 54.9, 56.2, 57.6, 59.0, 60.4, 61.9, 63.4, 64.9, 66.5,
                68.1, 69.8, 71.5, 73.2, 75.0, 76.8, 78.7, 80.6, 82.5, 84.5,
                86.6, 88.7, 90.9, 93.1, 95.3, 97.6],
    }

    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(12)

        top = QHBoxLayout()
        top.addWidget(QLabel("系列:"))
        self.combo = QComboBox()
        self.combo.addItems(list(self.SERIES.keys()))
        self.combo.currentIndexChanged.connect(self._reload)
        top.addWidget(self.combo)
        self.btn = self._copy_btn(None, "复制当前系列")
        self.btn.clicked.disconnect()
        self.btn.clicked.connect(self._copy_current)
        top.addWidget(self.btn)
        top.addStretch()
        layout.addLayout(top)

        self.table = self._table()
        layout.addWidget(self.table, 1)

        note = QLabel(
            "💡 标称值 = 基准值 × 10ⁿ (如 E24 的 12 → 1.2Ω / 12Ω / 120Ω / 1.2kΩ...)\n"
            "💡 容差参考: E6±20% / E12±10% / E24±5% / E48±2% / E96±1%"
        )
        note.setFont(system_font(9))
        note.setStyleSheet(
            "color: #6E6E73; background: #F5F7FA; border-radius: 6px;"
            "padding: 8px 12px;"
        )
        layout.addWidget(note)
        self._reload()

    def _reload(self):
        name = self.combo.currentText()
        vals = self.SERIES.get(name, [])
        rows = []
        # 3 列: 基准值 / 基准×10 / 基准×100
        for i in range(0, len(vals), 3):
            chunk = vals[i:i + 3]
            rows.append([self._fmt_v(v) for v in chunk] + [""] * (3 - len(chunk)))
        self._fill(self.table, ["基准值", "×10 (10·x)", "×100 (100·x)"], rows)
        self.btn.setEnabled(True)

    def _fmt_v(self, v):
        if v == int(v):
            return str(int(v))
        return f"{v:g}"

    def _copy_current(self):
        name = self.combo.currentText()
        vals = self.SERIES.get(name, [])
        text = f"{name}: " + ", ".join(self._fmt_v(v) for v in vals)
        from PyQt6.QtWidgets import QApplication
        QApplication.clipboard().setText(text)
        self.btn.setText("✓ 已复制")
        from PyQt6.QtCore import QTimer
        QTimer.singleShot(1500, lambda: self.btn.setText("复制当前系列"))


# =====================================================================
# Tab 4: 接口引脚速查
# =====================================================================
class _InterfaceTab(_LookupTab):
    """常用接口引脚定义速查"""

    DATA = [
        ("UART (TTL)", "TX / RX / GND", "3.3V 或 5V 电平; TX↔RX 交叉连接"),
        ("RS232 (DB9)", "2=TXD / 3=RXD / 5=GND", "±3~15V 电平; 交叉线; 需电平转换芯片"),
        ("RS485", "A(+) / B(−)", "差分半双工; 120Ω 终端匹配; 手拉手接线"),
        ("I2C", "SDA / SCL / GND", "开漏 + 上拉 (4.7kΩ@400kbps); 地址 7/10bit"),
        ("SPI", "MOSI / MISO / SCK / CS", "全双工主从; CS 低有效; 时钟极性 CPOL/CPHA"),
        ("USB 2.0 (Type-A)", "1=VCC 2=D− 3=D+ 4=GND", "VCC 5V; D+/D− 差分 90Ω 阻抗"),
        ("USB Type-C", "A1/B1=GND A4/B4=VBUS D+/D− 等", "CC 检测; 上下拉电阻 (Rp/Rd)"),
        ("JTAG (ARM)", "TMS / TCK / TDI / TDO / nRST", "5 线调试; 3.3V; TRST 可选"),
        ("SWD", "SWDIO / SWCLK / GND", "2 线调试 (比 JTAG 省引脚)"),
        ("CAN", "CANH / CANL", "差分; 两端各 120Ω; 波特率需一致"),
        ("RJ45 (以太网)", "1=橙白 2=橙 3=绿白 6=绿", "T568A/B; 1/2 发送, 3/6 接收"),
        ("ADC 输入", "VIN / VREF / GND", "输入阻抗低可能拉低分压; 建议加缓冲"),
        ("PWM 输出", "OUT / GND", "推挽输出; 注意驱动能力 (一般 <20mA)"),
    ]

    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(12)
        btn = self._copy_btn(None)
        top = QHBoxLayout()
        top.addWidget(btn)
        top.addStretch()
        layout.addLayout(top)
        table = self._table()
        self._fill(table, ["接口", "引脚定义", "说明"], self.DATA)
        layout.addWidget(table, 1)


# =====================================================================
# Tab 5: 贴片封装尺寸
# =====================================================================
class _PackageTab(_LookupTab):
    """贴片封装常见尺寸速查 (mm)"""

    DATA = [
        ("SOT-23", "3", "2.9 × 1.6", "1.9 × 0.95", "小信号管/稳压器"),
        ("SOT-23-5/6", "5/6", "2.9 × 1.6", "1.9 × 0.95", "LDO/电源芯片"),
        ("SOT-89", "3/5", "4.5 × 2.5", "4.0 × 2.0", "78Lxx/中功率管 (1W)"),
        ("SOT-223", "3/4", "6.5 × 3.5", "6.3 × 2.9", "AMS1117 等 1A LDO"),
        ("SOP-8", "8", "6.0 × 4.9", "5.8 × 3.9", "通用运放/接口芯片"),
        ("SOIC-16", "16", "10.3 × 7.5", "10.0 × 5.8", "多路驱动/控制"),
        ("SSOP-20", "20", "7.2 × 5.3", "6.4 × 4.3", "小间距 SOP"),
        ("TSSOP-16", "16", "5.0 × 4.4", "4.4 × 3.4", "窄体小引脚"),
        ("QFN-32", "32", "5.0 × 5.0", "3.6 × 3.6", "无引脚, 底部焊盘散热"),
        ("QFN-48", "48", "7.0 × 7.0", "5.5 × 5.5", "MCU 常用"),
        ("LQFP-48", "48", "9.0 × 9.0", "7.0 × 7.0", "带引脚 QFP"),
        ("LQFP-64", "64", "10.0 × 10.0", "7.0 × 7.0", "STM32F1 系列"),
        ("LQFP-100", "100", "14.0 × 14.0", "12.0 × 12.0", "STM32F4 系列"),
        ("BGA-100", "100", "10.0 × 10.0", "8.0 × 8.0", "球距 0.8mm"),
        ("BGA-144", "144", "12.0 × 12.0", "10.0 × 10.0", "球距 0.8mm"),
        ("SOD-123", "2", "2.7 × 1.6", "2.5 × 1.3", "二极管 (1N4148W)"),
        ("SMA/SMB", "2", "4.6 × 2.6", "4.3 × 2.4", "功率二极管/稳压"),
        ("SOT-363", "6", "2.1 × 1.25", "1.8 × 1.1", "射频/高速小管"),
    ]

    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(12)
        top = QHBoxLayout()
        top.addWidget(self._copy_btn(None))
        top.addStretch()
        layout.addLayout(top)
        table = self._table()
        self._fill(table, ["封装", "引脚数", "本体尺寸 (mm)", "焊盘尺寸 (mm)", "典型应用"],
                   self.DATA)
        layout.addWidget(table, 1)


# =====================================================================
# Tab 6: AWG 线规表
# =====================================================================
class _AwgTab(_LookupTab):
    """AWG 线规速查 (16~30AWG, 公式生成)"""

    RHO = 1.724e-8  # Ω·m 铜

    # 参考载流 (chassis wiring, A) — 经验值
    _AMP = {30: 0.2, 28: 0.5, 26: 0.8, 24: 1.2, 22: 2.0, 21: 2.5, 20: 3.0,
            19: 4.0, 18: 5.0, 17: 6.0, 16: 8.0}

    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(12)
        top = QHBoxLayout()
        top.addWidget(self._copy_btn(None))
        top.addStretch()
        layout.addLayout(top)

        rows = []
        for awg in range(30, 15, -1):  # 30 → 16
            d_mm = 0.127 * (92 ** ((36 - awg) / 39.0))
            area = math.pi / 4 * (d_mm / 1000) ** 2  # m²
            res_ohm_m = self.RHO / area
            rows.append([
                f"{awg} AWG",
                f"{d_mm * 10:.1f}",            # 直径 (0.1mm 单位显示为 mm)
                f"{area * 1e6:.3f}",           # 截面积 mm²
                f"{self._AMP.get(awg, '—')}",  # 载流 A
                f"{res_ohm_m * 1000:.1f}",     # mΩ/m
            ])
        table = self._table()
        self._fill(table, ["线规", "直径 (mm)", "截面积 (mm²)", "载流参考 (A)", "电阻 (mΩ/m)"],
                   rows)
        layout.addWidget(table, 1)

        note = QLabel(
            "💡 载流为 chassis wiring (单根明线) 经验参考值, 束线/高温环境需降额\n"
            "💡 直径 d = 0.127 × 92^((36−AWG)/39) mm; 常用电源线: 18AWG(1A), 16AWG(2A)"
        )
        note.setFont(system_font(9))
        note.setStyleSheet(
            "color: #6E6E73; background: #F5F7FA; border-radius: 6px;"
            "padding: 8px 12px;"
        )
        layout.addWidget(note)


# =====================================================================
# 主页面
# =====================================================================
class ReferenceLookupPage(QWidget):
    """常识速查合集: 色环电阻 + 单位换算 + E 系列 + 接口 + 封装 + AWG"""

    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(16)

        title = QLabel("📚 常识查询")
        title.setFont(system_font(20, weight=QFont.Weight.Bold))
        title.setStyleSheet(f"color: {TEXT};")
        layout.addWidget(title)

        subtitle = QLabel("电子常识速查: 色环电阻 / 单位换算 / E 系列标称值 / 接口引脚 / 封装尺寸 / AWG 线规")
        subtitle.setFont(system_font(10))
        subtitle.setStyleSheet(f"color: {TEXT_SECONDARY};")
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

        # Tab 0: 复用现有色环电阻页 (构造无参, 直接嵌入)
        from app.pages.resistor_color_code_page import ResistorColorCodePage
        tabs.addTab(ResistorColorCodePage(), "🎨 色环电阻")

        tabs.addTab(_UnitConvertTab(), "📐 单位换算")
        tabs.addTab(_ESeriesTab(), "🔢 E 系列标称值")
        tabs.addTab(_InterfaceTab(), "🔌 接口引脚")
        tabs.addTab(_PackageTab(), "📦 封装尺寸")
        tabs.addTab(_AwgTab(), "🪢 AWG 线规")
        inner_layout.addWidget(tabs, 1)
        scroll.setWidget(inner)

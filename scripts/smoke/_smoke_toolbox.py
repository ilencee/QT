# -*- coding: utf-8 -*-
"""冒烟: HardwareToolboxPage 实例化 + 各 Tab calculate (offscreen)"""
import os, sys

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
sys.path.insert(0, r"c:\Users\86249\Desktop\Github\QT")

from PyQt6.QtWidgets import QApplication, QTabWidget

app = QApplication([])
from app.pages.hardware_toolbox_page import (
    HardwareToolboxPage, DcdcBuckTab, ThermalTab, BiasDriveTab,
    CrystalTab, PcbTraceTab, BatteryTab, BaudTimerTab,
)

for cls in (DcdcBuckTab, ThermalTab, BiasDriveTab, CrystalTab,
            PcbTraceTab, BatteryTab, BaudTimerTab):
    w = cls()
    w.calculate()
    print(f"  OK {cls.__name__}")
    w.deleteLater()

page = HardwareToolboxPage()
tabs = page.findChild(QTabWidget)
print(f"  OK HardwareToolboxPage, tabs={tabs.count()}")
assert tabs.count() == 8, f"硬件工具箱应有 8 个 Tab (含 LDO 降压), 实际 {tabs.count()}"
for i in range(tabs.count()):
    print(f"    [{i}] {tabs.tabText(i)}")
page.close()
print("SMOKE_OK")

# -*- coding: utf-8 -*-
"""冒烟: ReferenceLookupPage 实例化 + 单位换算联动 (offscreen)"""
import os, sys

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
sys.path.insert(0, r"c:\Users\86249\Desktop\Github\QT")

from PyQt6.QtWidgets import QApplication, QTabWidget

app = QApplication([])
from app.pages.reference_lookup_page import (
    ReferenceLookupPage, _UnitConvertTab, _ESeriesTab, _InterfaceTab,
    _PackageTab, _AwgTab,
)

for cls in (_UnitConvertTab, _ESeriesTab, _InterfaceTab, _PackageTab, _AwgTab):
    w = cls()
    print(f"  OK {cls.__name__}")
    w.deleteLater()

page = ReferenceLookupPage()
tabs = page.findChild(QTabWidget)
print(f"  OK ReferenceLookupPage, tabs={tabs.count()}")
for i in range(tabs.count()):
    print(f"    [{i}] {tabs.tabText(i)}")

# 单位换算联动验证: 设置 dBm=10 → mW=10, Vrms=0.707
ut = _UnitConvertTab()
ut._edits[("rf", "dBm")].setText("10")
print(f"  dBm=10 → mW={ut._edits[('rf','mW')].text()}, Vrms={ut._edits[('rf','Vrms')].text()}")
ut._edits[("res", "kΩ")].setText("1")
print(f"  1kΩ → Ω={ut._edits[('res','Ω')].text()}, MΩ={ut._edits[('res','MΩ')].text()}")
ut.deleteLater()
page.close()
print("SMOKE_OK")

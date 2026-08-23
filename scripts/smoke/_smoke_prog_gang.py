"""稳定截图: 中微爱芯 → iWriterGang-4"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from PyQt6.QtWidgets import QApplication
from app.pages.programming_software_page import ProgrammingSoftwarePage

app = QApplication(sys.argv)
w = ProgrammingSoftwarePage()
w.resize(960, 720)
w.show()
app.processEvents()
for b, n in w._chip_map:
    if n == "中微爱芯":
        b.setChecked(True)
        w._update_detail(n)
        break
# 选 Gang-4
for i in range(w.programmer_combo.count()):
    if "Gang" in w.programmer_combo.itemText(i):
        w.programmer_combo.setCurrentIndex(i)
        w._render_detail("中微爱芯")
        break
app.processEvents()
w.grab().save(str(Path(__file__).parent / "_smoke_prog_gang.png"))
print("下拉:", [w.programmer_combo.itemText(i) for i in range(w.programmer_combo.count())])
print("chip:", w.current_chip())
print("programmer:", w._current_programmer().get("name"))
print("OK")

"""烧录页平铺 tab 冒烟: 实例化 + tab 联动 + 离屏截图"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from PyQt6.QtWidgets import QApplication

from app.pages.programming_software_page import ProgrammingSoftwarePage

app = QApplication(sys.argv)
w = ProgrammingSoftwarePage()
w.resize(960, 700)
w.show()
app.processEvents()

# 1) 厂商 tab 数量与选中态
tabs = [(name, btn.isChecked()) for btn, name in w._chip_map]
print("tabs:", tabs)

# 2) 切换到兆易创新: 烧录器下拉应联动为 3 项
for btn, name in w._chip_map:
    if name == "兆易创新":
        btn.setChecked(True)
        w._update_detail(name)
app.processEvents()
progs = [w.programmer_combo.itemText(i) for i in range(w.programmer_combo.count())]
print("兆易创新 programmers:", progs)
assert len(progs) == 3, "兆易创新应有 3 个烧录器"
assert w.current_chip() == "兆易创新"

# 3) 切换回第一个厂商
first = w._chip_map[0]
first[0].setChecked(True)
w._update_detail(first[1])
app.processEvents()
print("back to:", w.current_chip())

# 4) 截图 (离屏无中文字体时中文可能显示为方块, 仅预览限制, 不影响运行)
w.grab().save(str(Path(__file__).parent / "_smoke_prog_tab.png"))
print("SMOKE_OK")

"""中微爱芯多烧录器 + 全厂商 exe 路径解析冒烟"""
import os
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


def switch(name):
    for b, n in w._chip_map:
        if n == name:
            b.setChecked(True)
            w._update_detail(name)
            return


# 1) 中微爱芯 3 款烧录器
switch("中微爱芯")
names = [w.programmer_combo.itemText(i) for i in range(w.programmer_combo.count())]
print("中微爱芯下拉:", names)
assert len(names) == 3, "中微爱芯应有 3 款烧录软件"
assert "iWriterGang-4" in names[1] and "i_WRITER" in names[2]

# 2) 全厂商 exe 解析
ok, miss = 0, []
for b, n in w._chip_map:
    w._update_detail(n)
    for i in range(w.programmer_combo.count()):
        w.programmer_combo.setCurrentIndex(i)
        w._render_detail(n)
        p = w._current_programmer()
        exe = (p or {}).get("exe", "")
        if not exe:
            continue
        r = w._resolve_exe(exe)
        if r and os.path.isfile(r):
            ok += 1
        else:
            miss.append((n, p.get("name"), exe))
print(f"可解析 exe: {ok}, 失败: {miss}")
assert not miss, miss

w.grab().save(str(Path(__file__).parent / "_smoke_prog_multi.png"))
print("SMOKE_OK")

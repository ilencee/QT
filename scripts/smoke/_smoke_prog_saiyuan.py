"""赛元双烧录器冒烟: 下拉 2 项 + exe 解析 + 截图"""
import os
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from PyQt6.QtWidgets import QApplication
from app.pages.programming_software_page import ProgrammingSoftwarePage

app = QApplication(sys.argv)
w = ProgrammingSoftwarePage()
w.resize(1000, 720)
w.show()
app.processEvents()

def switch_chip(name: str):
    """切换到指定厂商 tab, 不存在时明确报错 (避免静默失败误导定位)"""
    for btn, chip in w._chip_map:
        if chip == name:
            btn.setChecked(True)
            w._update_detail(name)
            return
    raise AssertionError(f"厂商 tab 不存在: {name}")


# 1) 切到赛元
switch_chip("赛元")
app.processEvents()
progs = [w.programmer_combo.itemText(i) for i in range(w.programmer_combo.count())]
print("赛元烧录器:", progs)
assert len(progs) == 2, "赛元应有 2 款烧录软件"

# 2) 两款 exe 都能解析到真实文件; image 能解析(单图或多图)且渲染出图片
for i in range(w.programmer_combo.count()):
    w.programmer_combo.setCurrentIndex(i)
    w._render_detail("赛元")
    app.processEvents()
    p = w._current_programmer()
    assert p is not None, "赛元应有烧录器配置"
    exe = p.get("exe") or ""
    r = w._resolve_exe(exe)
    print(f"  [{p.get('name')}] -> {r}")
    assert r and os.path.isfile(r), exe
    paths = w._image_paths(p)
    print(f"  [image] {p.get('image')!r} -> {paths}")
    assert paths, f"image 未解析: {p.get('image')!r}"
    assert all(os.path.isfile(x) for x in paths), "image 应全部指向真实文件"
    assert w._current_pixmaps, "详情卡片应渲染出烧录器图片"
    assert w._current_pixmaps[0] is not None and not w._current_pixmaps[0].isNull()

# 3) 切到 SOC Pro51 截图 (找不到则显式失败, 避免截到错误状态)
pro51_idx = next(
    (i for i in range(w.programmer_combo.count()) if "Pro51" in w.programmer_combo.itemText(i)),
    None,
)
assert pro51_idx is not None, "赛元下拉中应存在 SOC Pro51 选项"
w.programmer_combo.setCurrentIndex(pro51_idx)
w._render_detail("赛元")
app.processEvents()
print("SOC Pro51: pixmaps=", len(w._current_pixmaps),
      "layout count=", w._image_layout.count(),
      "image_label hidden=", not w.image_label.isVisible())
w.grab().save(str(Path(__file__).parent / "_smoke_prog_saiyuan.png"))
print("SMOKE_OK")

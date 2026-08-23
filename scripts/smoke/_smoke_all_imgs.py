"""全量烧录器图片冒烟: 遍历所有厂商所有烧录器, 验证 image 解析 + pixmap 渲染

- 有 image 配置的: 必须全部解析到真实文件且渲染出非空 pixmap
- 无 image 配置的 (如 GD-Link): 跳过, 不判失败 (详情卡片应显示占位提示)
"""
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from PyQt6.QtWidgets import QApplication
from app.pages.programming_software_page import ProgrammingSoftwarePage

app = QApplication(sys.argv)
w = ProgrammingSoftwarePage()
w.resize(1000, 760)
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


total = imaged = ok = skipped = 0
for btn, chip in w._chip_map:
    switch_chip(chip)
    app.processEvents()
    n = w.programmer_combo.count()
    print(f"\n== {chip} ({n} 款) ==")
    for i in range(n):
        w.programmer_combo.setCurrentIndex(i)
        w._render_detail(chip)
        app.processEvents()
        p = w._current_programmer()
        assert p is not None, f"{chip} 第 {i} 项无配置"
        total += 1
        name = p.get("name") or "?"
        img = p.get("image") or ""
        if not img:
            print(f"  [-] {name}: 无 image (跳过)")
            skipped += 1
            continue
        imaged += 1
        paths = w._image_paths(p)
        assert paths, f"{name} image 未解析: {img!r}"
        assert all(os.path.isfile(x) for x in paths), f"{name} 图片文件缺失: {paths}"
        assert w._current_pixmaps, f"{name} 未渲染出图片"
        assert all(not x.isNull() for x in w._current_pixmaps), f"{name} 存在空 pixmap"
        ok += 1
        print(f"  [OK] {name}: {len(paths)} 图 {[Path(x).name for x in paths]}")

print(f"\n汇总: 共 {total} 款, 有图 {imaged} 款全过 ({ok}), 无图跳过 {skipped} 款")
assert ok == imaged == total - skipped, "有 image 的烧录器必须全部渲染成功"
w.close()
print("SMOKE_OK")

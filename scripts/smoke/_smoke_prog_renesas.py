"""瑞萨烧录软件冒烟: tab 出现 + 联动 + 官网按钮 + 四图渲染 + 截图"""
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


# 1) tab 数量 (>= 5) 与瑞萨存在性
tabs = [n for _, n in w._chip_map]
print("厂商 tabs:", tabs)
assert "瑞萨" in tabs, "缺少瑞萨 tab"
assert len(tabs) >= 5, f"厂商 tab 数量异常: {len(tabs)}"

# 2) 切换到瑞萨
switch_chip("瑞萨")
app.processEvents()
progs = [w.programmer_combo.itemText(i) for i in range(w.programmer_combo.count())]
print("瑞萨烧录器:", progs)
assert progs == ["Renesas Flash Programmer (RFP)"]
assert w.current_chip() == "瑞萨"

# 3) 官网按钮可用 (RFP 有官网)
assert w.website_btn.isEnabled(), "RFP 应有官网, 按钮应可用"
print("website btn tooltip:", w.website_btn.toolTip())

# 4) exe 为空 -> 启动会走文件选择对话框 (这里只验证解析为空)
p = w._current_programmer()
assert p is not None, "瑞萨应有烧录器配置"
assert p.get("exe") == ""
print("exe 为空 (本地未安装, 点击启动会弹出选择对话框)")

# 5) RFP 四图 (E2/E2 Lite/E1/E20) 全部解析到真实文件且渲染出图片
paths = w._image_paths(p)
print(f"  [image] {p.get('image')!r} -> {paths}")
assert len(paths) == 4, f"RFP 应配 4 张调试器图片: {paths}"
assert all(os.path.isfile(x) for x in paths), "image 应全部指向真实文件"
assert w._current_pixmaps, "详情卡片应渲染出烧录器图片"
assert w._current_pixmaps[0] is not None and not w._current_pixmaps[0].isNull()
print("RFP 四图解析 + 渲染 OK")

# 6) 截图确认 tab 一行放下、四图垂直排列、整体美观
app.processEvents()
w.grab().save(str(Path(__file__).parent / "_smoke_prog_renesas.png"))
print("SMOKE_OK")

# -*- coding: utf-8 -*-
"""临时冒烟测试: 一芯片多烧录器"""
import json
import os
import sys
import tempfile

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from PyQt6.QtWidgets import QApplication

app = QApplication([])

from app.pages.programming_software_page import ProgrammingSoftwarePage

# --- UI: 多烧录器下拉与渲染 ---
page = ProgrammingSoftwarePage()
page.show()
idx = page.chip_combo.findText("兆易创新")
assert idx >= 0, "兆易创新缺失"
page.chip_combo.setCurrentIndex(idx)
names = [page.programmer_combo.itemText(i) for i in range(page.programmer_combo.count())]
print("兆易创新烧录器:", names)
assert "XW16Pro Standalone Programmer" in names
assert "FT200" in names
assert "GD32 All-In-One Programmer / GD-Link Utility" in names

page.programmer_combo.setCurrentText("FT200")
md = page.detail_browser.toPlainText()
assert "FT200" in md and "兆易创新" in md
assert page._current_exe_candidates() == [], "FT200 未配置 exe, 候选应为空"

page.programmer_combo.setCurrentText("XW16Pro Standalone Programmer")
assert len(page._current_exe_candidates()) >= 1, "XW16Pro 应有候选路径"
resolved = page._resolve_exe(page._current_exe_candidates()[0])
print("XW16Pro 解析:", resolved)
assert resolved and os.path.isfile(resolved), "相对路径应解析为存在的文件"

# 其他芯片: 每芯片至少 1 个烧录器
for c in range(page.chip_combo.count()):
    page.chip_combo.setCurrentIndex(c)
    assert page.programmer_combo.count() >= 1, f"{page.chip_combo.currentText()} 无烧录器"
print("所有芯片烧录器数量 OK")

# --- 迁移: 旧平铺结构 → programmers (临时文件, 不污染真实配置) ---
old = {
    "programming_software": {
        "chips": {
            "测试芯片": {
                "software": "OldProg",
                "exe": r"C:\tools\old.exe",
                "desc": "desc",
                "hardware": "hw",
                "usage": "usage",
                "note": "note",
            }
        }
    }
}
with tempfile.TemporaryDirectory() as td:
    tmp = os.path.join(td, "config.json")
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(old, f, ensure_ascii=False)
    from app.core.config_manager import ConfigManager

    page2 = ProgrammingSoftwarePage()
    page2.cfg = ConfigManager(tmp)
    page2.chips = {"测试芯片": {}}
    page2._migrate_chips_structure()
    progs = page2.cfg.config["programming_software"]["chips"]["测试芯片"]["programmers"]
    assert isinstance(progs, list) and len(progs) == 1
    assert progs[0]["name"] == "OldProg"
    assert progs[0]["exe"] == r"C:\tools\old.exe"
    assert progs[0]["desc"] == "desc"
    print("旧结构迁移 OK:", progs[0])

print("ALL PASS")

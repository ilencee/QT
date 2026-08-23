"""已安装烧录软件自动发现冒烟: 关键词配置 + 注册表/开始菜单/目录三级扫描 + 详情回填

不启动任何程序, 只验证搜索与回填逻辑.
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

CHIPS = [chip for _, chip in w._chip_map]


def switch_chip(name: str):
    for btn, chip in w._chip_map:
        if chip == name:
            btn.setChecked(True)
            w._update_detail(name)
            return
    raise AssertionError(f"厂商 tab 不存在: {name}")

# 1) 所有烧录器都有 search_keywords
missing = []
for _, chip in w._chip_map:
    for prog in w._current_programmers(chip) or []:
        if not w._search_keywords(prog):
            missing.append(f"{chip} / {prog.get('name')}")
assert not missing, f"以下烧录器缺少 search_keywords: {missing}"
print(f"OK 全部 {sum(len(w._current_programmers(c) or []) for c in CHIPS)} 款烧录器已配 search_keywords")

# 2) 真实系统三级扫描不抛异常, 打印检测结果
print("\n== 本机安装检测 ==")
total_installed = 0
for chip in CHIPS:
    switch_chip(chip)
    app.processEvents()
    for i in range(w.programmer_combo.count()):
        w.programmer_combo.setCurrentIndex(i)
        w._render_detail(chip)
        app.processEvents()
        prog = w._current_programmer()
        if not prog:
            continue
        name = prog.get("name", "?")
        kws = w._search_keywords(prog)
        paths = w._find_installed(kws)
        if paths:
            total_installed += 1
            print(f"  [已安装] {chip} · {name}: {paths[0]} ({len(paths)} 候选)")
        else:
            print(f"  [未安装] {chip} · {name}")
print(f"\n本机检测到 {total_installed} 款已安装烧录软件")

# 3) 详情回填: 切换到一个烧录器, 等待后台线程回填 "正在检测…" 占位被替换
switch_chip(CHIPS[0])
app.processEvents()
w.programmer_combo.setCurrentIndex(0)
w._render_detail(CHIPS[0])
for _ in range(60):  # 最多等 6s
    app.processEvents()
    md = w.detail_browser.toMarkdown()
    if "正在检测" not in md:
        break
    import time
    time.sleep(0.1)
assert "正在检测" not in w.detail_browser.toMarkdown(), "检测结果未回填"
print(f"\nOK 详情回填: {w.detail_browser.toMarkdown().splitlines()[-1].strip()}")

# 4) _launch 自动发现分支: mock _find_installed 返回假路径, 验证走自动启动而不是弹警告
import unittest.mock as mock

fake_exe = os.path.join(str(Path(__file__).parent), "_fake_prog.exe")
with open(fake_exe, "wb") as f:
    f.write(b"MZ")

launched = []
with mock.patch.object(w, "_find_installed", return_value=[fake_exe]), \
     mock.patch.object(w, "_resolve_exe", return_value=""), \
     mock.patch.object(w, "_start_and_activate", side_effect=lambda p: launched.append(p)), \
     mock.patch.object(w, "_prompt_pick_exe"):
    w._launch()
assert launched == [fake_exe], f"_launch 应自动启动已安装软件: {launched}"
os.remove(fake_exe)
print("\nOK _launch 配置路径缺失时自动启动已安装软件")
w.close()
print("\nSMOKE_OK")

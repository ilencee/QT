# -*- coding: utf-8 -*-
"""验证: 绿色版为安装包时, 启动/检测优先已安装版本, 不再打开安装向导"""
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

from PyQt6.QtWidgets import QApplication
import app.pages.programming_software_page as m
from app.pages.programming_software_page import ProgrammingSoftwarePage

app = QApplication(sys.argv)
page = ProgrammingSoftwarePage()
fail = []


def check(name, cond, extra=""):
    print(f"{'PASS' if cond else 'FAIL'} | {name}" + (f" | {extra}" if extra else ""))
    if not cond:
        fail.append(name)


# 1. 安装包特征识别
_root = Path(__file__).resolve().parents[2]
saiyuan_pkg = _root / \
    "烧录软件/赛元/SOC Programming Tool Enhance v1.80(LIB1D00)/SOC Programming Tool Enhance v1.80(LIB1D00).exe"
iwriter = _root / \
    "烧录软件/中微爱芯/iWriterPro V1.3.09 build04273/iWriterPro.exe"
check("赛元绿色版识别为安装包", page._is_installer_package(str(saiyuan_pkg)))
check("中微爱芯绿色版非安装包", not page._is_installer_package(str(iwriter)))

# 2. 定位赛元并切换
target_chip = target_prog = None
for _, chip in page._chip_map:
    for p in page._current_programmers(chip) or []:
        if "SOC Programming Tool" in p.get("name", ""):
            target_chip, target_prog = chip, p
            break
    if target_prog:
        break
for btn, chip in page._chip_map:
    if chip == target_chip:
        btn.setChecked(True)
        page._update_detail(target_chip)
        break
for i in range(page.programmer_combo.count()):
    if page.programmer_combo.itemText(i) == target_prog["name"]:
        page.programmer_combo.setCurrentIndex(i)
        break
page._render_detail(target_chip)

# 3. 点启动: 应直接启动已安装版本, 不再弹确认窗 (提速关键)
launched = []
page._start_and_activate = lambda p: launched.append(p)
dialogs = []

def fake_info(*a, **kw):
    dialogs.append(("information", a[2] if len(a) > 2 else a))
    return None

def fake_question(*a, **kw):
    dialogs.append(("question", a[2] if len(a) > 2 else a))
    return m.QMessageBox.StandardButton.No

m.QMessageBox.information = staticmethod(fake_info)
m.QMessageBox.question = staticmethod(fake_question)

page._installed_cache.clear()
page._launch()
installed_paths = page._find_installed(["SOC Programming Tool", "SOC", "SC-LINK"], force_rescan=True)
print("已安装候选:", installed_paths)
check("直接启动已安装版本(非安装包)", len(launched) == 1 and launched[0] in installed_paths, str(launched))
check("无阻塞弹窗(零交互直接启动)", len(dialogs) == 0, str(dialogs)[:150])
check("按钮已给出启动反馈", page.launch_btn.text().startswith("⏳") and not page.launch_btn.isEnabled(),
      page.launch_btn.text())

# 4. 详情页检测行
page._detection_pending.discard(target_prog["name"])
page._render_detail(target_chip)
for _ in range(30):
    app.processEvents()
    md = page.detail_browser.toMarkdown()
    if "正在检测" not in md:
        break
    time.sleep(0.1)
for ln in md.splitlines():
    if "**本机软件**" in ln:
        print("详情行:", ln.strip())
        check("详情显示已检测到安装(非绿色版可用)", "已检测到安装" in ln, ln.strip())
        break

page.close()
app.quit()

print("\n" + ("=== 全部通过 ===" if not fail else f"=== {len(fail)} 项失败: {fail} ==="))
sys.exit(1 if fail else 0)

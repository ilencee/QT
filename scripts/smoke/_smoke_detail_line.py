# -*- coding: utf-8 -*-
"""验证: 10 款烧录器详情页"本机软件"检测行 (绿色版可用/已安装/未检测到)"""
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

from PyQt6.QtWidgets import QApplication
from app.pages.programming_software_page import ProgrammingSoftwarePage

app = QApplication(sys.argv)
page = ProgrammingSoftwarePage()


def switch_chip(name):
    for btn, chip in page._chip_map:
        if chip == name:
            btn.setChecked(True)
            page._update_detail(name)
            return


lines = []
for _, chip in page._chip_map:
    switch_chip(chip)
    app.processEvents()
    for i in range(page.programmer_combo.count()):
        page.programmer_combo.setCurrentIndex(i)
        page._render_detail(chip)
        for _ in range(30):  # 最多等 3s 回填
            app.processEvents()
            md = page.detail_browser.toMarkdown()
            if "正在检测" not in md:
                break
            time.sleep(0.1)
        md = page.detail_browser.toMarkdown()
        for ln in md.splitlines():
            if "**本机软件**" in ln or "本机软件:" in ln:
                lines.append((chip, ln.strip()))
                break

for chip, ln in lines:
    print(f"[{chip}] {ln}")
page.close()
app.quit()

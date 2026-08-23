"""已安装检测 UI 截图: 赛元(已安装) + 瑞萨(未安装) 详情"""
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from PyQt6.QtWidgets import QApplication
from app.pages.programming_software_page import ProgrammingSoftwarePage

app = QApplication(sys.argv)
w = ProgrammingSoftwarePage()
w.resize(1000, 760)
w.show()
app.processEvents()


def switch_chip(name):
    for btn, chip in w._chip_map:
        if chip == name:
            btn.setChecked(True)
            w._update_detail(name)
            return


# 赛元 (本机已安装 SOC 软件) -> 等检测结果回填
switch_chip("赛元")
app.processEvents()
for _ in range(60):
    app.processEvents()
    if "正在检测" not in w.detail_browser.toMarkdown():
        break
    time.sleep(0.1)
w.grab().save(str(Path(__file__).resolve().parent / "_smoke_installed_saiyuan.png"))

# 瑞萨 (未安装) -> 等检测结果回填
switch_chip("瑞萨")
app.processEvents()
for _ in range(60):
    app.processEvents()
    if "正在检测" not in w.detail_browser.toMarkdown():
        break
    time.sleep(0.1)
w.grab().save(str(Path(__file__).resolve().parent / "_smoke_installed_renesas.png"))
print("截图完成")

"""烧录页官网字段冒烟: 按钮状态 + 详情渲染 + 浏览器打开逻辑"""
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


def switch_chip(name):
    for btn, n in w._chip_map:
        if n == name:
            btn.setChecked(True)
            w._update_detail(name)
            break


def prog_website(name):
    for p in w._current_programmers(name):
        print(f"  - {p.get('name')}: website={p.get('website')!r}")
    return w._current_programmers(name)


# 1) 中微爱芯: 官网按钮应可用
switch_chip("中微爱芯")
assert w.website_btn.isEnabled(), "iWriterPro 应有官网, 按钮应可用"
md = w.detail_browser.toPlainText()
assert "官网" in md and "官方下载/更新页面" in md, "详情应含官网链接"
print("中微爱芯 OK, website_btn tooltip:", w.website_btn.toolTip())

# 2) 兆易创新: XW16Pro/All-In-One 有官网, FT200 无官网
switch_chip("兆易创新")
progs = prog_website("兆易创新")
for i, p in enumerate(progs):
    w.programmer_combo.setCurrentIndex(i)
    w._render_detail("兆易创新")
    enabled = w.website_btn.isEnabled()
    print(f"  兆易[{p.get('name')}] button_enabled={enabled}")
    if p.get("name") == "FT200":
        assert not enabled, "FT200 无官网, 按钮应禁用"
    else:
        assert enabled, f"{p.get('name')} 应有官网"
# 切回 FT200 确认禁用
w.programmer_combo.setCurrentIndex(1)
w._render_detail("兆易创新")
assert not w.website_btn.isEnabled()

# 3) 十速 / 赛元
switch_chip("十速")
assert w.website_btn.isEnabled()
switch_chip("赛元")
assert w.website_btn.isEnabled()

# 4) _open_website 不报错 (不真的打开浏览器)
prog = w._current_programmer()
print("赛元 website:", prog.get("website"))

# 5) 截图
w.grab().save(str(Path(__file__).parent / "_smoke_prog_website.png"))
print("SMOKE_OK")

"""冒烟测试: 硬件工具箱/常识查询页面接线 (offscreen)。

验证: 主窗口导航 8 项 / 页面工厂 8 项 / 新页面可切换 / 首页卡片 7 张。
用法: python scripts/smoke/_smoke_pages.py
"""

import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt6.QtWidgets import QApplication

from app.core.config_manager import app_root
from app.main_window import SerialDebugTool


def main():
    cfg_path = app_root() / "config.json"
    backup = cfg_path.read_bytes() if cfg_path.exists() else None
    try:
        _run()
        print("SMOKE_PAGES_OK")
    finally:
        if backup is not None:
            cfg_path.write_bytes(backup)
        else:
            try:
                cfg_path.unlink()
            except FileNotFoundError:
                pass


def _run():
    app = QApplication([])
    win = SerialDebugTool()
    win.show()
    app.processEvents()

    # 1. 导航 7 项 / 工厂 7 项 (功率变换已并入硬件工具箱)
    names = [n[1] for n in win.nav_items]
    assert len(win.nav_items) == 7, f"导航应为 7 项, 实际 {len(win.nav_items)}"
    assert names[4] == "硬件工具箱" and names[5] == "常识查询" and names[6] == "系统设置"
    assert len(win._page_factories) == 7, "页面工厂应为 7 项"

    # 2. 首页卡片 6 张 (未隐藏时)
    home = win._pages[0]
    cards = sum(
        1 for i in range(home.grid.count())
        if home.grid.itemAt(i).widget() is not None
    )
    assert cards == 6, f"首页应有 6 张卡片, 实际 {cards}"

    # 3. 切换硬件工具箱 (含 LDO 降压 Tab)
    win.switch_page(4)
    app.processEvents()
    from app.pages.hardware_toolbox_page import HardwareToolboxPage
    assert isinstance(win._pages[4], HardwareToolboxPage), "索引4应为硬件工具箱页"
    from PyQt6.QtWidgets import QTabWidget
    assert win._pages[4].findChild(QTabWidget).count() == 8, "硬件工具箱应有 8 个 Tab"

    # 4. 切换常识查询 (速查合集)
    win.switch_page(5)
    app.processEvents()
    from app.pages.reference_lookup_page import ReferenceLookupPage
    assert isinstance(win._pages[5], ReferenceLookupPage), "索引5应为常识速查页"
    assert win._pages[5].findChild(QTabWidget).count() == 6, "常识速查应有 6 个 Tab"

    # 5. 设置页可见栏目 7 项 (栏目显隐卡片)
    from app.pages.settings_page import SettingsPage
    sp = SettingsPage(nav_items=win.nav_items)
    app.processEvents()
    assert len(sp._vis_checks) == 7, "设置页栏目卡片应为 7 项"

    # 6. 全部页面工厂可实例化 (逐个创建并删除, 验证延迟导入无遗漏)
    for idx in range(len(win._page_factories)):
        win.switch_page(idx)
        app.processEvents()
    # 确认所有页面已实例化
    for idx in range(len(win._page_factories)):
        assert idx in win._pages, f"页面 {idx} 未实例化"
    win.switch_page(5)
    app.processEvents()
    assert win.stacked_widget.currentWidget() is win._pages[5]

    win.close()
    app.processEvents()


if __name__ == "__main__":
    main()

"""冒烟测试: 栏目显隐功能 (设置页勾选 / 右键菜单回调 / 首页同步 / 持久化)。

- QT_QPA_PLATFORM=offscreen 无界面运行
- 测试前备份 config.json, 结束后恢复, 不污染真实配置
用法: python scripts/smoke/_smoke_visibility.py
"""

import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt6.QtWidgets import QApplication

from app.core.config_manager import ConfigManager, app_root
from app.main_window import SerialDebugTool


def main():
    cfg_path = app_root() / "config.json"
    backup = cfg_path.read_bytes() if cfg_path.exists() else None
    try:
        _run()
        print("SMOKE_VISIBILITY_OK")
    finally:
        # 恢复真实配置 (测试中可能写入了隐藏栏目/窗口状态)
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

    assert win._hidden_pages == set(), f"初始应无隐藏栏目, 实际 {win._hidden_pages}"

    # 1. 应用隐藏: 串口调试(1) + 硬件工具箱(4)  [功率变换已并入硬件工具箱, 无独立栏目]
    hidden = {"串口调试", "硬件工具箱"}
    win._apply_page_visibility(hidden)
    app.processEvents()
    assert not win.nav_buttons[1].isVisible(), "串口调试按钮应隐藏"
    assert not win.nav_buttons[4].isVisible(), "硬件工具箱按钮应隐藏"
    assert win.nav_buttons[0].isVisible() and win.nav_buttons[6].isVisible(), "锁定栏目应可见"
    home = win._pages[0]
    assert home._hidden_pages == hidden, "首页 hidden 状态应同步"
    # 首页卡片数量: _TOOLS 共 6 张(索引1-6), 隐藏 2 张后剩 4 张
    cards = sum(
        1 for i in range(home.grid.count())
        if home.grid.itemAt(i).widget() is not None
    )
    assert cards == 4, f"首页应剩 4 张卡片, 实际 {cards}"

    # 2. 隐藏当前正在显示的栏目 → 自动切到第一个可见栏目(首页锁定)
    win.switch_page(1)
    app.processEvents()
    assert win.stacked_widget.currentWidget() is win._pages[1], "当前页应为串口调试"
    win._apply_page_visibility(hidden)
    app.processEvents()
    assert win.stacked_widget.currentWidget() is win._pages[0], "隐藏当前页后应自动回首页"
    assert win.nav_buttons[0].isChecked(), "首页导航按钮应为选中态"

    # 3. 右键菜单勾选回调 (模拟菜单项 toggled)
    win._on_nav_menu_toggled(2, "文本润色", False)
    app.processEvents()
    assert "文本润色" in win._hidden_pages and not win.nav_buttons[2].isVisible()
    win._on_nav_menu_toggled(2, "文本润色", True)
    app.processEvents()
    assert "文本润色" not in win._hidden_pages and win.nav_buttons[2].isVisible()

    # 4. 设置页卡片: 构造(带回调) → 取消勾选常识查询 → 主窗口联动
    from app.pages.settings_page import SettingsPage
    sp = SettingsPage(on_visibility_changed=win._apply_page_visibility, nav_items=win.nav_items)
    app.processEvents()
    cb = sp._vis_checks[5]
    assert cb.isChecked(), "常识查询初始应为勾选 (未隐藏)"
    cb.setChecked(False)
    app.processEvents()
    assert "常识查询" in win._hidden_pages, "设置页取消勾选应隐藏常识查询"
    assert not win.nav_buttons[5].isVisible(), "主窗口导航按钮应同步隐藏"
    cb.setChecked(True)
    app.processEvents()
    assert "常识查询" not in win._hidden_pages
    assert win.nav_buttons[5].isVisible()

    # 5. 持久化: 经 _on_nav_menu_toggled 已写配置, 重启等价读取
    saved = set(win._cfg.get_window_config().get("hidden_pages", []) or [])
    assert saved == win._hidden_pages, f"配置持久化不一致: {saved} != {win._hidden_pages}"

    # 6. 锁定栏目: 设置页固定显示, 菜单禁用
    assert not sp._vis_checks[0].isEnabled() and not sp._vis_checks[6].isEnabled(), "锁定栏目应禁用"
    assert sp._vis_checks[0].isChecked() and sp._vis_checks[6].isChecked(), "锁定栏目应勾选"

    # 7. 无参构造兼容 (诊断脚本等直接实例化)
    sp2 = SettingsPage()
    app.processEvents()
    assert len(sp2._vis_checks) == 7, "无参构造应有 7 个栏目勾选框"

    win.close()
    app.processEvents()


if __name__ == "__main__":
    main()

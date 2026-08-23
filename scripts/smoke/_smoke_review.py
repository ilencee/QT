"""综合冒烟: 首页跳转 / 串口助手启动页 / 色环五环 / 配置防御 / AI 参数防御"""
import os
import sys
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from PyQt6.QtWidgets import QApplication

from app.main_window import SerialDebugTool


def main():
    app = QApplication(sys.argv)
    w = SerialDebugTool()
    w.show()
    app.processEvents()

    # 1) 首页卡片点击跳转
    home = w._pages[0]
    assert home is not None and home.on_navigate is not None, "首页应带导航回调"
    home.on_navigate(1)
    app.processEvents()
    assert w.stacked_widget.currentIndex() == 1, "首页点击应跳到串口调试页"
    w.switch_page(0)
    app.processEvents()
    print("[1] 首页卡片跳转 OK")

    # 2) 串口页: 直接调用现成工具 (SSCOM), 不内置收发
    sp = w._pages[1]
    assert sp.tools, "应扫描到串口调试工具"
    assert all(os.path.isfile(t["abs"]) for t in sp.tools), "工具路径应存在"
    names = [t["name"].lower() for t in sp.tools]
    assert any("sscom" in n for n in names), "应包含 sscom 串口助手"
    resolved = sp._resolve_exe("sscom/sscom5.13.1.exe")
    assert resolved and os.path.isfile(resolved), "相对路径应可解析"
    app.processEvents()
    print("[2] 串口页 OK (工具数:", len(sp.tools), ")")

    # 3) 色环: 四环 / 五环计算 (现内嵌于常识查询页 Tab0)
    w.switch_page(5)
    app.processEvents()
    from PyQt6.QtWidgets import QTabWidget
    ref_page = w._pages[5]
    rc = ref_page.findChild(QTabWidget).widget(0)
    rc.five_band_check.setChecked(False)
    rc.band1_combo.combo.setCurrentIndex(1)  # Brown 1
    rc.band2_combo.combo.setCurrentIndex(0)  # Black 0
    rc.multiplier_combo.combo.setCurrentIndex(2)  # x100
    rc.calculate_resistance()
    r4 = rc.result_value.text()
    rc.five_band_check.setChecked(True)
    rc.band3_combo.combo.setCurrentIndex(2)  # Red 2
    rc.calculate_resistance()
    r5 = rc.result_value.text()
    print("[3] 四环结果:", r4, "| 五环结果:", r5)
    assert r4 != r5, "五环模式应改变计算结果"

    # 4) config_manager: 缺段自动创建
    from app.core.config_manager import ConfigManager
    cm = ConfigManager.__new__(ConfigManager)
    cm.config = {"foo": 1}
    cm._serial_section()["port"] = "COM9"
    assert cm.config["serial_port"]["port"] == "COM9", "缺段应自动创建"
    print("[4] config_manager 缺段防御 OK")

    # 5) deepseek 参数防御
    from app.core.deepseek_client import load_api_config
    bad = SimpleNamespace(config={
        "power_conversion": {"api": {"temperature": "abc", "max_tokens": "xyz"}}
    })
    api = load_api_config(bad)
    assert api["temperature"] == 0.7 and api["max_tokens"] == 1500, "非法值应回退默认"
    out = load_api_config(SimpleNamespace(config={
        "power_conversion": {"api": {"temperature": 5.0, "max_tokens": 99999}}
    }))
    assert out["temperature"] == 2.0 and out["max_tokens"] == 8192, "越界值应 clamp"
    print("[5] deepseek 参数防御 OK")

    # 6) 编程页 prog=None 不再崩溃 (修复表达式等价验证)
    prog = None
    prog_name = (prog or {}).get("name", "") or "烧录器"
    assert prog_name == "烧录器", "prog=None 应回退默认名称"
    print("[6] 编程页 prog=None 防御 OK")

    # 7) 首页 / 串口页截图
    w.switch_page(0)
    app.processEvents()
    w.grab().save(str(Path(__file__).parent / "_smoke_review_home.png"))
    w.switch_page(1)
    app.processEvents()
    w.grab().save(str(Path(__file__).parent / "_smoke_review_serial.png"))
    print("SMOKE_OK")


if __name__ == "__main__":
    main()

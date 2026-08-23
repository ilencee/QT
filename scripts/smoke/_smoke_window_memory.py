# -*- coding: utf-8 -*-
"""窗口位置/大小 + 导航栏状态记忆冒烟 (off-window 测试)

- 无记录时默认 1200x800@(100,100), nav_expanded=True
- closeEvent 保存 geometry + nav_expanded
- 再次实例化恢复保存的位置/大小/状态
"""
import os
import sys
import io
import json

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

# 用临时 config 副本, 不污染真实 config.json
import shutil
_root = Path(__file__).resolve().parents[2]
real_cfg = os.path.join(str(_root), 'config.json')
tmp_cfg = os.path.join(str(_root), '_cfg_tmp.json')
shutil.copy(real_cfg, tmp_cfg)

from PyQt6.QtWidgets import QApplication
from PyQt6.QtCore import Qt
import app.main_window as mw

app = QApplication([])

# 1) 首次: 无 x/y/nav 记录 → 默认值
mw.ConfigManager = lambda f: mw.ConfigManager  # 不替换, 保持真实类
orig_main = mw.main  # 防止误调 main

import types
class FakeCfg:
    def __init__(self, f):
        self.config = json.load(open(tmp_cfg, encoding='utf-8'))
    def get_window_config(self):
        return self.config.get("window", {})
    def save_config(self):
        json.dump(self.config, open(tmp_cfg, 'w', encoding='utf-8'), ensure_ascii=False, indent=2)
    @property
    def cfg(self):
        return self

# 打补丁: main_window 里的 ConfigManager 引用换掉 (main_window 已 import 名字)
real_cm = mw.ConfigManager
mw.ConfigManager = FakeCfg

try:
    w1 = mw.SerialDebugTool()
    g1 = w1.geometry()
    assert g1.width() == 1200 and g1.height() == 800, f"默认大小 {g1.width()}x{g1.height()}"
    assert w1.nav_expanded is True, "默认导航展开"

    # 2) 模拟用户调整窗口 + 收起导航 + 保存
    w1.move(321, 222)
    w1.resize(1366, 768)
    w1.toggle_nav_bar()  # 收起
    assert w1.nav_expanded is False, "收起后应为 False"
    assert w1.nav_frame.width() == 70, "收起后宽度 70"
    w1._save_window_state()
    w2 = mw.SerialDebugTool()
    g2 = w2.geometry()
    assert g2.x() == 321 and g2.y() == 222, f"恢复位置 ({g2.x()},{g2.y()})"
    assert g2.width() == 1366 and g2.height() == 768, f"恢复大小 {g2.width()}x{g2.height()}"
    assert w2.nav_expanded is False, "恢复收起状态"
    assert w2.nav_frame.width() == 70, f"导航栏应为收起宽度70, 实际 {w2.nav_frame.width()}"

    # 3) 再次恢复展开
    w2.toggle_nav_bar()
    assert w2.nav_expanded is True, "展开后应为 True"
    w2._save_window_state()
    w3 = mw.SerialDebugTool()
    assert w3.nav_expanded is True, "恢复展开状态"
    assert w3.nav_frame.width() == 200, "导航栏应为展开宽度200"

    print("OK 默认1200x800; 保存321,222/1366x768/收起; 恢复一致; 再恢复展开")
    print("SMOKE_OK")
finally:
    mw.ConfigManager = real_cm
    os.remove(tmp_cfg)

# -*- coding: utf-8 -*-
"""临时冒烟测试: 自动识别烧录按钮 + 边界修复"""
import os
import sys

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from PyQt6.QtWidgets import QApplication

app = QApplication([])

from app.pages import programming_software_page as m
from app.pages.programming_software_page import ProgrammingSoftwarePage

# 1) 模块级 Win32 工具与默认关键词
assert m.DEFAULT_BURN_KEYWORDS, "默认关键词缺失"
print("默认关键词:", m.DEFAULT_BURN_KEYWORDS)

# 2) 页面构造 + 自动烧录开关
page = ProgrammingSoftwarePage()
page.show()
assert page.auto_burn_check.isChecked() is False, "自动烧录默认应关闭"
print("auto_burn_check OK")

# 3) 边界修复: 脏数据过滤
page.chips = {
    "脏芯片": {
        "programmers": [None, "bad", {"name": "好烧录器", "exe": ""}, 123],
    }
}
progs = page._current_programmers("脏芯片")
assert progs == [{"name": "好烧录器", "exe": ""}], f"脏数据过滤失败: {progs}"
print("脏数据过滤 OK:", progs)

# 4) 关键词: 默认 / 配置覆盖
page.chip_combo.clear()
page.chip_combo.addItem("脏芯片")
page.chip_combo.setCurrentIndex(0)
kw_default = page._burn_keywords()
print("关键词默认:", kw_default)
assert kw_default == m.DEFAULT_BURN_KEYWORDS
page.chips["脏芯片"]["programmers"][0]["auto_burn_keywords"] = ["点火", "GO"]
assert page._burn_keywords() == ("点火", "GO"), "配置覆盖失败"
print("关键词覆盖 OK")

# 5) 直接调用 Win32 识别函数不抛异常 (枚举自身进程窗口)
import ctypes

own_pid = os.getpid()
root = m._find_top_window_by_pid(own_pid)  # 本进程无可见窗口, 应返回 None 或某窗口
print("自进程窗口查找:", root)
hit = m._find_button_by_keywords(0, m.DEFAULT_BURN_KEYWORDS) if root else None
print("按钮识别(空句柄安全):", hit)

# 6) _start_and_activate 返回 PID 的契约: 用假路径验证失败分支
failed_pid = page._start_and_activate(r"C:\nonexistent_dir_xyz\no.exe")
assert failed_pid is None, "启动失败应返回 None"
print("启动失败分支 OK (弹窗已在 offscreen 下返回 None)")

print("ALL PASS")

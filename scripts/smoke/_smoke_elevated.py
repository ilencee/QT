# -*- coding: utf-8 -*-
"""WinError 740 (需要管理员权限) 启动处理冒烟

- Popen 抛 740 → 走 ShellExecute 触发 UAC, 不弹启动失败窗
- 正常启动仍走 Popen
- ShellExecute 失败 (如用户取消 UAC) → 弹提示
- 真实调用 _start_via_shell 验证 c_ssize_t 修复 (会触发 UAC, 手动点是)
"""
import os
import sys
import subprocess
import io
from unittest import mock

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from PyQt6.QtWidgets import QApplication, QMessageBox
from app.pages.programming_software_page import ProgrammingSoftwarePage

app = QApplication([])
w = ProgrammingSoftwarePage()

fake_exe = os.path.join(os.path.dirname(os.path.abspath(__file__)), "_fake740.exe")
open(fake_exe, "wb").write(b"MZ")


def err740(*a, **k):
    e = OSError(740, "The requested operation requires elevation")
    e.winerror = 740
    raise e


warnings = []
launched_shell = []

# 1) Popen 抛 740 → 走 ShellExecute, 不弹警告
with mock.patch.object(subprocess, "Popen", side_effect=err740), \
     mock.patch.object(w, "_start_via_shell",
                       side_effect=lambda p: launched_shell.append(p) or True), \
     mock.patch.object(QMessageBox, "warning",
                       side_effect=lambda *a, **k: warnings.append(a)):
    w._start_and_activate(fake_exe)
assert launched_shell == [fake_exe], f"740 应走 ShellExecute: {launched_shell}"
assert not warnings, f"740 不应弹警告: {warnings}"

# 2) Popen 成功 → 走 Popen, 不触发 shell
launched_shell.clear()
with mock.patch.object(subprocess, "Popen") as mp, \
     mock.patch.object(w, "_start_via_shell",
                       side_effect=lambda p: launched_shell.append(p) or True):
    w._start_and_activate(fake_exe)
assert mp.called, "正常启动应走 Popen"
assert not launched_shell, "正常启动不应走 ShellExecute"

# 3) ShellExecute 失败 (用户取消 UAC) → 弹提示
before = len(warnings)
with mock.patch.object(subprocess, "Popen", side_effect=err740), \
     mock.patch.object(w, "_start_via_shell", return_value=False), \
     mock.patch.object(QMessageBox, "warning",
                       side_effect=lambda *a, **k: warnings.append(a)):
    w._start_and_activate(fake_exe)
assert len(warnings) > before, "shell 失败时应弹提示"

# 4) .lnk 快捷方式 740 → 也走 ShellExecute
launched_shell.clear()
fake_lnk = os.path.join(os.path.dirname(os.path.abspath(__file__)), "_fake740.lnk")
open(fake_lnk, "wb").write(b"L")
with mock.patch.object(os, "startfile", side_effect=err740), \
     mock.patch.object(w, "_start_via_shell",
                       side_effect=lambda p: launched_shell.append(p) or True), \
     mock.patch.object(QMessageBox, "warning",
                       side_effect=lambda *a, **k: warnings.append(a)):
    w._start_and_activate(fake_lnk)
assert launched_shell == [fake_lnk], f".lnk 740 应走 ShellExecute: {launched_shell}"
os.remove(fake_lnk)

os.remove(fake_exe)
print("OK 740→ShellExecute(UAC); 正常→Popen; shell失败→提示; lnk 740→ShellExecute")

# 5) 真实调用: c_ssize_t 修复后应返回 True (会触发 UAC, 请手动点是)
soc51 = r"C:\Program Files (x86)\SOC\SOC Pro51 v5.20\SOC Pro51.exe"
if os.path.isfile(soc51):
    ok = w._start_via_shell(soc51)
    print(f"_start_via_shell({soc51}) -> {ok}  (True=已提交 UAC, 请点是)")
    assert ok, "c_ssize_t 修复后 _start_via_shell 应返回 True"
else:
    print("未安装 SOC Pro51, 跳过真实调用")

print("SMOKE_OK")

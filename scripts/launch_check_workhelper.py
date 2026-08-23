# -*- coding: utf-8 -*-
"""启动 dist\工作助手_单文件\工作助手.exe 并检查是否正常出现主窗口（验证序数错误是否修复）。
用法: python launch_check_workhelper.py          # 仅启动
      python launch_check_workhelper.py --check  # 检查窗口与进程
"""
import subprocess
import sys
import time

import ctypes
from ctypes import wintypes

EXE = r"c:\Users\86249\Desktop\Github\QT\dist\工作助手_单文件\工作助手.exe"
TITLE = "工作助手"


def enum_windows():
    results = []

    @ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)
    def cb(hwnd, lparam):
        if not ctypes.windll.user32.IsWindowVisible(hwnd):
            return True
        length = ctypes.windll.user32.GetWindowTextLengthW(hwnd)
        if length == 0:
            return True
        buf = ctypes.create_unicode_buffer(length + 1)
        ctypes.windll.user32.GetWindowTextW(hwnd, buf, length + 1)
        results.append(buf.value)
        return True

    ctypes.windll.user32.EnumWindows(cb, 0)
    return results


def proc_exists():
    r = subprocess.run(
        ["tasklist", "/fi", "imagename eq 工作助手.exe", "/fo", "csv"],
        capture_output=True, text=True, encoding="gbk", errors="replace",
    )
    return "工作助手.exe" in r.stdout


def main():
    if len(sys.argv) > 1 and sys.argv[1] == "--check":
        print("process exists:", proc_exists())
        wins = enum_windows()
        hit = [w for w in wins if TITLE in w]
        print("titles:", wins)
        print("main window found:", bool(hit))
        return
    # 启动
    try:
        p = subprocess.Popen([EXE])
        print("launched pid:", p.pid)
    except Exception as e:
        print("LAUNCH FAILED:", e)
        sys.exit(1)
    # 等 12 秒让 bootloader 解压 + 加载 Python
    time.sleep(12)
    print("after 12s -> process exists:", proc_exists())
    wins = enum_windows()
    print("titles:", wins)
    print("main window found:", TITLE in str(wins))


if __name__ == "__main__":
    main()

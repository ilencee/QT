# -*- coding: utf-8 -*-
"""把 build_*.bat 从 UTF-8 转码为 GBK(ANSI)，修复 cmd 下中文注释乱码导致脚本无法执行。"""
import io
import os

base = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
files = ["build_exe_onefile.bat", "build_exe.bat"]

for name in files:
    p = os.path.join(base, name)
    with io.open(p, encoding="utf-8-sig") as f:
        data = f.read()
    data = data.replace("\r\n", "\n").replace("\n", "\r\n")
    with io.open(p, "w", encoding="gbk", newline="") as f:
        f.write(data)
    # 验证可读回
    with io.open(p, encoding="gbk") as f:
        check = f.read()
    ok = "PyInstaller" in check and "打包" in check
    print(name, "converted to GBK, verify:", ok)

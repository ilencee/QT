# -*- coding: utf-8 -*-
"""把 build_*.bat 的 --icon 改为绝对路径(%~dp0assets\app.ico)，避免 PyInstaller 按 spec 目录解析相对图标路径。"""
import io
import os

base = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
files = ["build_exe_onefile.bat", "build_exe.bat"]

for name in files:
    p = os.path.join(base, name)
    with io.open(p, encoding="gbk") as f:
        data = f.read()
    old = '"assets/app.ico"'
    new = '"%~dp0assets\\app.ico"'
    n = data.count(old)
    if n:
        data = data.replace(old, new)
        with io.open(p, "w", encoding="gbk", newline="") as f:
            f.write(data)
    print(name, "replaced icon path:", n)

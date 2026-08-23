# -*- coding: utf-8 -*-
"""用系统最新 VC 运行库(14.50)覆盖 Python 打包环境中的旧版 DLL，修复 PyInstaller 打包 exe 的"无法定位序数"错误。"""
import os
import shutil

sys32 = os.path.join(os.environ["WINDIR"], "System32")

targets = {
    os.path.join(os.environ["LOCALAPPDATA"], "Programs", "Python", "Python39"): [
        "VCRUNTIME140.dll", "VCRUNTIME140_1.dll",
    ],
    os.path.join(os.environ["LOCALAPPDATA"], "Programs", "Python", "Python39",
                 "lib", "site-packages", "PyQt6", "Qt6", "bin"): [
        "VCRUNTIME140.dll", "VCRUNTIME140_1.dll",
        "MSVCP140.dll", "MSVCP140_1.dll", "MSVCP140_2.dll", "CONCRT140.dll",
    ],
}

for d, names in targets.items():
    if not os.path.isdir(d):
        print("MISSING DIR:", d)
        continue
    for n in names:
        src = os.path.join(sys32, n)
        dst = os.path.join(d, n)
        if not os.path.exists(src):
            print("SKIP no sys32 copy:", n)
            continue
        if not os.path.exists(dst):
            print("SKIP not present:", dst)
            continue
        bak = dst + ".bak"
        if not os.path.exists(bak):
            shutil.copy2(dst, bak)
        shutil.copy2(src, dst)
        print("UPDATED:", dst)

print("done")

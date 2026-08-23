# -*- coding: utf-8 -*-
"""诊断：定位 Python 打包环境中的 VC 运行库 DLL 版本（排查"无法定位序数"）。"""
import os
import subprocess
import sys

names = [
    "VCRUNTIME140.dll", "VCRUNTIME140_1.dll",
    "MSVCP140.dll", "MSVCP140_1.dll", "MSVCP140_2.dll",
    "MSVCP140_codecvt_ids.dll", "CONCRT140.dll",
]

bases = [
    sys.prefix,
    os.path.join(sys.prefix, "DLLs"),
    os.path.join(sys.prefix, "lib", "site-packages", "PyQt6", "Qt6", "bin"),
]


def version_of(path):
    try:
        r = subprocess.run(
            ["powershell", "-NoProfile", "-Command",
             '(Get-Item "{}").VersionInfo.FileVersion'.format(path.replace("\\", "\\\\"))],
            capture_output=True, text=True, timeout=30,
        )
        return r.stdout.strip() or "?"
    except Exception as e:
        return "ERR:" + str(e)


def main():
    for base in bases:
        if not os.path.isdir(base):
            continue
        print("---", base)
        for n in names:
            p = os.path.join(base, n)
            if os.path.exists(p):
                print("   {:<28} {}  ({} bytes)".format(n, version_of(p), os.path.getsize(p)))
    print()
    print("--- System32 (对照) ---")
    for n in names:
        p = os.path.join(os.environ["WINDIR"], "System32", n)
        if os.path.exists(p):
            print("   {:<28} {}  ({} bytes)".format(n, version_of(p), os.path.getsize(p)))


if __name__ == "__main__":
    main()

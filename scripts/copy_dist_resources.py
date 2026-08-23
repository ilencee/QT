# -*- coding: utf-8 -*-
"""把运行资源复制到打包输出目录（等价 build_exe_*.bat 的 [4/5] 步）。"""
import os
import shutil

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DST = os.path.join(BASE, "dist", "工作助手_单文件")

for rel in ["config.json", "assets", "烧录软件", "串口调试助手"]:
    src = os.path.join(BASE, rel)
    dst = os.path.join(DST, rel)
    if os.path.isfile(src):
        shutil.copy2(src, dst)
        print("copied file :", rel)
    elif os.path.isdir(src):
        if os.path.exists(dst):
            shutil.rmtree(dst)
        shutil.copytree(src, dst)
        print("copied dir  :", rel)
    else:
        print("MISSING     :", rel)

print("done ->", DST)

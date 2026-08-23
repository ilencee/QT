# -*- coding: utf-8 -*-
"""修复验证: 缓存空结果导致"已安装仍找不到"的 bug 复测
1. 空结果不再缓存 → 安装后重扫能立即发现
2. force_rescan 跳过缓存 → 点击启动必重扫
3. 本机真实检测: 赛元 SOC 工具能找到
"""
import os
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

from PyQt6.QtWidgets import QApplication
from app.pages.programming_software_page import ProgrammingSoftwarePage

app = QApplication(sys.argv)
page = ProgrammingSoftwarePage()
fail = []


def check(name, cond, extra=""):
    print(f"{'PASS' if cond else 'FAIL'} | {name}" + (f" | {extra}" if extra else ""))
    if not cond:
        fail.append(name)


# 真实存在的文件, 用于模拟"已安装的 exe"
real_file = os.path.abspath(__file__)

# 保存原始扫描方法 (第 3 部分需要恢复)
_orig_reg = page._scan_registry_uninstall
_orig_sm = page._scan_start_menu
_orig_cd = page._scan_common_dirs

# ---- 1. 空结果不缓存 ----
page._installed_cache.clear()
kw = ["FooTool", "FOO"]
calls = {"n": 0}


def fake_scan(keywords):
    calls["n"] += 1
    return []


page._scan_registry_uninstall = fake_scan
page._scan_start_menu = fake_scan
page._scan_common_dirs = fake_scan

r1 = page._find_installed(kw)
cache_key = tuple(sorted(k.lower() for k in kw))
check("空结果返回空", r1 == [] and calls["n"] == 3, f"scan次数={calls['n']}")
check("空结果未进缓存", cache_key not in page._installed_cache)

# 第二次调用仍会重扫 (模拟用户已安装)
page._scan_common_dirs = lambda k: [real_file]
r2 = page._find_installed(kw)
check("安装后重扫能发现", r2 == [real_file], str(r2))
check("发现后已缓存", cache_key in page._installed_cache)

# ---- 2. 非空结果缓存 + force_rescan 跳过缓存 ----
calls2 = {"n": 0}


def fake_scan2(keywords):
    calls2["n"] += 1
    return [real_file]


page._scan_registry_uninstall = fake_scan2
page._scan_start_menu = fake_scan2
page._scan_common_dirs = fake_scan2
r3 = page._find_installed(kw)
n_after_first = calls2["n"]
r4 = page._find_installed(kw)  # 命中缓存, 不再扫描
check("非空结果命中缓存", r3 == r4 == [real_file] and calls2["n"] == n_after_first,
      f"scan次数={calls2['n']}")
r5 = page._find_installed(kw, force_rescan=True)  # 强制重扫
check("force_rescan 跳过缓存", calls2["n"] == n_after_first + 3,
      f"scan次数={calls2['n']} (期望 {n_after_first + 3})")

# ---- 3. 本机真实检测: 赛元已安装 ----
page._scan_registry_uninstall = _orig_reg
page._scan_start_menu = _orig_sm
page._scan_common_dirs = _orig_cd
page._installed_cache.clear()
start = time.time()
real = page._find_installed(["SOC Programming Tool", "SOC", "SC-LINK"], force_rescan=True)
elapsed = time.time() - start
check("真实扫描找到赛元(本机已安装)", len(real) > 0, f"{len(real)} 个候选, 耗时 {elapsed:.2f}s")
for p in real:
    print("      ->", p)

page.close()
app.quit()

print("\n" + ("=== 全部通过 ===" if not fail else f"=== {len(fail)} 项失败: {fail} ==="))
sys.exit(1 if fail else 0)

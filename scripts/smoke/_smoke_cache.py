# -*- coding: utf-8 -*-
"""已安装发现缓存冒烟: 装过一次后点启动直接命中记忆, 不再重复扫描

- 场景A(已装): 首次启动扫描1次并缓存 → 之后每次启动不再扫描, 直接启动
- 场景B(未装): 空结果不缓存 → 每次启动都会重新扫描 (保证新装后能立即发现)
- 场景C(装了又卸载): 缓存命中但文件不存在 → 触发重扫 → 找不到 → 弹"未找到"
- 场景D(后来新装): 之前空结果不缓存 → 重扫发现新安装 → 直接启动
"""
import os
import sys
import io
from unittest import mock

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from PyQt6.QtWidgets import QApplication, QMessageBox
from app.pages.programming_software_page import ProgrammingSoftwarePage

app = QApplication([])
w = ProgrammingSoftwarePage()

KW = ["SOC Pro51", "Pro51"]
cache_key = tuple(sorted(k.lower() for k in KW))

# 用一个真实存在的假 exe 模拟已安装
fake = os.path.join(os.path.dirname(os.path.abspath(__file__)), "_fake_installed.exe")
open(fake, "wb").write(b"MZ")

scan_calls = {"n": 0}
def fake_scan(keywords):
    scan_calls["n"] += 1
    return [fake]

# A) 已装: 第一次 force_rescan 扫描并缓存
w._installed_cache.pop(cache_key, None)
scan_calls["n"] = 0
with mock.patch.object(w, "_scan_registry_uninstall", side_effect=fake_scan), \
     mock.patch.object(w, "_scan_start_menu", side_effect=fake_scan), \
     mock.patch.object(w, "_scan_common_dirs", side_effect=fake_scan):
    r1 = w._find_installed(KW, force_rescan=True)
    assert r1 == [fake], f"A1 首次应找到: {r1}"
    assert scan_calls["n"] >= 1, "A1 首次应执行扫描"
    n_after_first = scan_calls["n"]

    # A2) 再次调用 (不带 force_rescan) → 命中缓存, 不扫描
    r2 = w._find_installed(KW)
    assert r2 == [fake], f"A2 应命中缓存: {r2}"
    assert scan_calls["n"] == n_after_first, "A2 命中缓存不应再扫描"

    # A3) 第三次也一样
    r3 = w._find_installed(KW)
    assert scan_calls["n"] == n_after_first, "A3 命中缓存不应再扫描"

# B) 未装: 空结果不缓存, 每次重扫
w._installed_cache.pop(cache_key, None)
scan_calls["n"] = 0
with mock.patch.object(w, "_scan_registry_uninstall", return_value=[]), \
     mock.patch.object(w, "_scan_start_menu", return_value=[]), \
     mock.patch.object(w, "_scan_common_dirs", return_value=[]):
    b1 = w._find_installed(KW)
    assert b1 == [], f"B1 空结果: {b1}"
    assert cache_key not in w._installed_cache, "B 空结果不应缓存"
    b2 = w._find_installed(KW)
    assert b2 == [], f"B2 空结果: {b2}"

# C) 缓存命中但文件被删 → 调用处过滤后触发重扫
w._installed_cache[cache_key] = [fake]
os.remove(fake)  # 模拟卸载
with mock.patch.object(w, "_scan_registry_uninstall", return_value=[]), \
     mock.patch.object(w, "_scan_start_menu", return_value=[]), \
     mock.patch.object(w, "_scan_common_dirs", return_value=[]):
    hit = [p for p in w._find_installed(KW) if os.path.exists(p)]
    assert hit == [], "C 缓存路径已失效应被过滤"
    # 调用处: 无有效结果 → force_rescan 重扫
    rescanned = [p for p in w._find_installed(KW, force_rescan=True) if os.path.exists(p)]
    assert rescanned == [], "C 重扫后仍为空"

# D) 后来新装: 之前空(未缓存) → 重扫立即发现
open(fake, "wb").write(b"MZ")  # 模拟新安装
scan_calls["n"] = 0
with mock.patch.object(w, "_scan_registry_uninstall", side_effect=fake_scan), \
     mock.patch.object(w, "_scan_start_menu", return_value=[]), \
     mock.patch.object(w, "_scan_common_dirs", return_value=[]):
    d1 = w._find_installed(KW, force_rescan=True)
    assert d1 == [fake], f"D 新装后重扫应发现: {d1}"

w._installed_cache.clear()
# 清理测试写入的磁盘记忆文件, 避免 fake 路径污染用户真实记忆 (下次启动时会重新扫描生成)
mem = os.path.join(str(Path(__file__).resolve().parents[2]), "installed_programs_memory.json")
if os.path.exists(mem):
    os.remove(mem)
print("OK A已装→命中缓存不重扫; B未装→空不缓存每次重扫; C卸载→缓存失效触发重扫; D新装→立即发现")
print("SMOKE_OK")

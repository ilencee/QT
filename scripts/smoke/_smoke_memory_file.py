# -*- coding: utf-8 -*-
"""已安装发现记忆文件冒烟: 扫描结果落盘, 重启直接读记忆不再重扫

- A) 首次扫描 → 写盘记忆文件; 新建实例(模拟重启) → 读记忆直接命中, 零扫描
- B) 从未安装 → 空结果不写盘, 每次重扫 (新装后第一次点启动立即发现)
- C) 装了又卸载 → 记忆路径失效 → 重扫空 → 记忆条目从文件清理
- D) 后来新装 → 重扫发现 → 重新写盘
- E) 记忆文件损坏/缺失 → 静默降级, 重新扫描不崩溃
"""
import io
import json
import os
import sys
import tempfile
from unittest import mock

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from PyQt6.QtWidgets import QApplication
from app.pages.programming_software_page import ProgrammingSoftwarePage

app = QApplication([])
w = ProgrammingSoftwarePage()

tmpdir = tempfile.mkdtemp(prefix="qt_mem_")
tmp_mem = os.path.join(tmpdir, "installed_programs_memory.json")

KW = ["SOC Pro51", "Pro51"]
cache_key = tuple(sorted(k.lower() for k in KW))
key_str = "|".join(cache_key)

fake = os.path.join(tmpdir, "_fake_installed.exe")
open(fake, "wb").write(b"MZ")

scan_calls = {"n": 0}
def fake_scan(keywords):
    scan_calls["n"] += 1
    return [fake]

def clear_all(cache):
    cache.clear()
    if os.path.exists(tmp_mem):
        os.remove(tmp_mem)

# A) 首次扫描 → 写盘; 重启实例读记忆零扫描
with mock.patch.object(w, "_installed_memory_file", return_value=tmp_mem), \
     mock.patch.object(w, "_scan_registry_uninstall", side_effect=fake_scan), \
     mock.patch.object(w, "_scan_start_menu", side_effect=fake_scan), \
     mock.patch.object(w, "_scan_common_dirs", side_effect=fake_scan):
    clear_all(w._installed_cache)
    r = w._find_installed(KW, force_rescan=True)
    assert r == [fake], f"A1 首次应找到: {r}"
    assert os.path.exists(tmp_mem), "A1 记忆文件应已写盘"
    data = json.load(open(tmp_mem, encoding="utf-8"))
    assert key_str in data["installed"], "A1 记忆文件应含该关键词组"
    assert data["installed"][key_str] == [fake], "A1 记忆文件路径应正确"

    # 模拟重启: 新实例从同一记忆文件加载
    w2 = ProgrammingSoftwarePage()
    with mock.patch.object(w2, "_installed_memory_file", return_value=tmp_mem):
        w2._load_installed_memory()
    scan_calls["n"] = 0
    with mock.patch.object(w2, "_scan_registry_uninstall", side_effect=fake_scan), \
         mock.patch.object(w2, "_scan_start_menu", side_effect=fake_scan), \
         mock.patch.object(w2, "_scan_common_dirs", side_effect=fake_scan):
        r2 = w2._find_installed(KW)
    assert r2 == [fake], f"A2 重启后应命中记忆: {r2}"
    assert scan_calls["n"] == 0, f"A2 命中记忆不应扫描, 实际扫描 {scan_calls['n']} 次"
    assert cache_key in w2._installed_cache, "A2 缓存应含记忆条目"

# B) 从未安装: 空结果不写盘, 每次重扫
with mock.patch.object(w, "_installed_memory_file", return_value=tmp_mem):
    clear_all(w._installed_cache)
    with mock.patch.object(w, "_scan_registry_uninstall", return_value=[]), \
         mock.patch.object(w, "_scan_start_menu", return_value=[]), \
         mock.patch.object(w, "_scan_common_dirs", return_value=[]):
        assert w._find_installed(KW) == [], "B 空结果"
        assert not os.path.exists(tmp_mem), "B 空结果不应写盘"
        assert cache_key not in w._installed_cache, "B 空结果不缓存"

# C) 装了又卸载: 记忆路径失效 → 重扫空 → 清理记忆文件条目
with mock.patch.object(w, "_installed_memory_file", return_value=tmp_mem):
    clear_all(w._installed_cache)
    w._installed_cache[cache_key] = [fake]
    w._save_installed_memory()
    assert os.path.exists(tmp_mem), "C 准备: 记忆已写盘"
    os.remove(fake)  # 模拟卸载
    with mock.patch.object(w, "_scan_registry_uninstall", return_value=[]), \
         mock.patch.object(w, "_scan_start_menu", return_value=[]), \
         mock.patch.object(w, "_scan_common_dirs", return_value=[]):
        w._find_installed(KW, force_rescan=True)
    assert cache_key not in w._installed_cache, "C 失效记忆应被清理"
    data = json.load(open(tmp_mem, encoding="utf-8"))
    assert key_str not in data["installed"], "C 记忆文件应清理失效条目"

# D) 后来新装: 重扫发现 → 写盘
with mock.patch.object(w, "_installed_memory_file", return_value=tmp_mem), \
     mock.patch.object(w, "_scan_registry_uninstall", side_effect=fake_scan), \
     mock.patch.object(w, "_scan_start_menu", return_value=[]), \
     mock.patch.object(w, "_scan_common_dirs", return_value=[]):
    open(fake, "wb").write(b"MZ")
    d1 = w._find_installed(KW, force_rescan=True)
    assert d1 == [fake], f"D 新装后应发现: {d1}"
    data = json.load(open(tmp_mem, encoding="utf-8"))
    assert key_str in data["installed"], "D 记忆文件应重新写盘"

# E) 记忆文件损坏 → 静默降级不崩溃, 重新扫描
with mock.patch.object(w, "_installed_memory_file", return_value=tmp_mem):
    open(tmp_mem, "w", encoding="utf-8").write("{ 损坏的 json !!")
    w._installed_cache.clear()
    w._load_installed_memory()  # 不应抛异常
    assert cache_key not in w._installed_cache, "E 损坏文件不产生记忆"
    with mock.patch.object(w, "_scan_registry_uninstall", side_effect=fake_scan), \
         mock.patch.object(w, "_scan_start_menu", return_value=[]), \
         mock.patch.object(w, "_scan_common_dirs", return_value=[]):
        e1 = w._find_installed(KW, force_rescan=True)
    assert e1 == [fake], f"E 损坏后应重新扫描: {e1}"

# 清理临时文件
if os.path.exists(fake):
    os.remove(fake)
if os.path.exists(tmp_mem):
    os.remove(tmp_mem)
os.rmdir(tmpdir)

print("OK 落盘记忆: A首次扫描写盘+重启零扫描; B空结果不写盘; C卸载清理记忆; D新装重新写盘; E损坏降级")
print("SMOKE_OK")

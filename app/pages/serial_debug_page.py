"""串口调试助手页: 直接调用现成串口调试工具 (SSCOM / 友善串口调试助手), 不内置收发功能"""

import os
import re
import subprocess
import winreg
from pathlib import Path

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QFont
from PyQt6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from app.core.config_manager import app_root

CARD_STYLE = "background: white; border: 1px solid #E4E7ED; border-radius: 10px;"
SECTION_TITLE_STYLE = (
    "font-size: 14px; font-weight: bold; color: #303133;"
    "background: transparent; border: none;"
)
LAUNCH_BTN_STYLE = (
    "QPushButton { background: #409EFF; color: white; border: none;"
    "border-radius: 8px; padding: 8px 20px; font-weight: bold; font-size: 13px; }"
    "QPushButton:hover { background: #66B1FF; }"
    "QPushButton:pressed { background: #337ECC; }"
)


class SerialDebugPage(QWidget):
    """串口调试: 直接启动现成串口工具, 不自己实现串口收发"""

    # 安装器特征字节 (识别"绿色版实为安装包", 与烧录软件页同款)
    _INSTALLER_PACKAGE_SIGS = (
        (b"Inno Setup", "Inno Setup 安装包"),
        (b"Nullsoft", "NSIS 安装包"),
        (b"InstallShield", "InstallShield 安装包"),
        (b"Setup Factory", "Setup Factory 安装包"),
        (b"WinRAR SFX", "WinRAR 自解压包"),
        (b"7-Zip SFX", "7-Zip 自解压包"),
        (b"WinZip Self-Extractor", "WinZip 自解压包"),
        (b"This installation was built with", "NSIS 安装包"),
    )

    def __init__(self, parent=None):
        super().__init__(parent)
        self.tools: list = []
        self._package_cache: dict = {}
        self._installed_cache: dict = {}  # 关键词组 -> 已安装路径列表 (内存缓存, 空结果不缓存)
        self._setup_ui()
        self._scan_tools()

    # ==================== 路径解析 ====================
    @staticmethod
    def _tools_dir() -> Path:
        """串口调试工具所在目录 (相对程序根目录)"""
        return app_root() / "串口调试助手"

    def _resolve_exe(self, rel: str) -> str:
        """相对 串口调试助手/ 的路径 → 绝对路径; 不存在返回空串"""
        if not rel:
            return ""
        try:
            path = self._tools_dir() / rel
            return str(path) if path.is_file() else ""
        except OSError:
            return ""

    # ==================== 安装包识别 ====================
    def _is_installer_package(self, path: str) -> bool:
        """判断 exe 是否实为安装包 (Inno/NSIS/InstallShield/SFX 等), 结果缓存

        安装包 exe 直接启动会进入安装向导 (重复安装);
        识别为安装包时 UI 标记"⚠ 安装包", 启动前需用户确认。
        """
        if not path or not os.path.isfile(path):
            return False
        key = path.lower()
        if key in self._package_cache:
            return self._package_cache[key]
        is_pkg = False
        try:
            with open(path, "rb") as f:
                head = f.read(1024 * 1024)  # 读前 1MB 搜安装器特征
            is_pkg = any(sig in head for sig, _ in self._INSTALLER_PACKAGE_SIGS)
        except OSError:
            is_pkg = False
        self._package_cache[key] = is_pkg
        return is_pkg

    # ==================== 已安装软件自动发现 ====================
    @staticmethod
    def _tool_keywords(tool: dict) -> list:
        """工具搜索关键词: 从 exe 名提取 (去版本号后的字母词组合 + 各单词兜底)"""
        stem = str(tool.get("name", "") or "")
        parts = [
            p for p in re.split(r"[^0-9A-Za-z\u4e00-\u9fff]+", stem)
            if p and not p.isdigit()
        ]
        words = [p for p in parts if len(p) >= 2]
        kws = []
        combined = " ".join(words)
        if combined:
            kws.append(combined)
        for w in words:
            if w not in kws:
                kws.append(w)
        return kws

    @staticmethod
    def _reg_value(sub_key, name: str):
        """读取注册表子键字符串值, 缺失返回空串"""
        try:
            val, _ = winreg.QueryValueEx(sub_key, name)
            return str(val) if val else ""
        except (OSError, ValueError):
            return ""

    @classmethod
    def _kw_score(cls, text: str, keywords: list) -> int:
        """关键词匹配得分: 命中关键词的最长长度, 0 表示未命中.

        短关键词(<4字符)必须词边界命中, 避免 "soc" 误配 "Social Club";
        长关键词子串命中即可 (安装名通常是 "软件全称 v版本").
        """
        t = text.lower()
        best = 0
        for k in keywords:
            kk = k.lower()
            if not kk:
                continue
            if len(kk) >= 4:
                hit = kk in t
            else:
                hit = re.search(rf"(?<![a-z0-9]){re.escape(kk)}(?![a-z0-9])", t) is not None
            if hit:
                best = max(best, len(kk))
        return best

    @staticmethod
    def _is_installer_exe(path: str) -> bool:
        """判断是否是卸载/安装器 exe (这类程序不应作为主程序启动)"""
        name = os.path.basename(path).lower()
        return (
            "uninst" in name
            or "setup" in name
            or "installer" in name
            or "卸载" in name
            or name.startswith("dpinst")  # DIFx 驱动安装器
        )

    def _scan_registry_uninstall(self, keywords: list) -> list:
        """从注册表卸载信息中查找已安装软件, 返回 exe 路径列表 (含 32/64 位视图)"""
        found = []
        hives = [
            (winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall"),
            (winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\WOW6432Node\Microsoft\Windows\CurrentVersion\Uninstall"),
            (winreg.HKEY_CURRENT_USER, r"SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall"),
        ]
        for hive, sub_path in hives:
            try:
                uninstall_key = winreg.OpenKey(hive, sub_path)
            except OSError:
                continue
            try:
                for i in range(winreg.QueryInfoKey(uninstall_key)[0]):
                    try:
                        sub_name = winreg.EnumKey(uninstall_key, i)
                        with winreg.OpenKey(uninstall_key, sub_name) as sub:
                            display = self._reg_value(sub, "DisplayName")
                            if not self._kw_score(display, keywords):
                                continue
                            exe = ""
                            icon = self._reg_value(sub, "DisplayIcon")
                            if icon:
                                exe = icon.split(",")[0].strip().strip('"')
                            if self._is_installer_exe(exe):
                                loc = self._reg_value(sub, "InstallLocation")
                                exe = (
                                    self._find_exe_in(loc, keywords)
                                    if loc and os.path.isdir(loc)
                                    else ""
                                )
                            elif not exe:
                                loc = self._reg_value(sub, "InstallLocation")
                                if loc and os.path.isdir(loc):
                                    exe = self._find_exe_in(loc, keywords)
                            if exe and os.path.isfile(exe):
                                found.append(exe)
                    except OSError:
                        continue
            finally:
                winreg.CloseKey(uninstall_key)
        return found

    def _scan_start_menu(self, keywords: list) -> list:
        """扫描开始菜单快捷方式, 返回匹配关键词的 .lnk 路径列表"""
        roots = [
            os.path.join(os.environ.get("ProgramData", ""), "Microsoft", "Windows", "Start Menu", "Programs"),
            os.path.join(os.environ.get("APPDATA", ""), "Microsoft", "Windows", "Start Menu", "Programs"),
        ]
        found = []
        for root in roots:
            if not os.path.isdir(root):
                continue
            for dirpath, _, files in os.walk(root):
                for f in files:
                    if not f.lower().endswith(".lnk"):
                        continue
                    if self._is_installer_exe(f):  # 跳过"卸载 xxx"快捷方式
                        continue
                    if self._kw_score(f, keywords):
                        found.append(os.path.join(dirpath, f))
        return found

    def _scan_common_dirs(self, keywords: list) -> list:
        """扫描常见安装目录 (Program Files 等), 仅深入目录名含关键词的目录"""
        roots = []
        for env in ("ProgramFiles", "ProgramFiles(x86)"):
            v = os.environ.get(env)
            if v and os.path.isdir(v):
                roots.append(v)
        la = os.environ.get("LOCALAPPDATA")
        if la and os.path.isdir(os.path.join(la, "Programs")):
            roots.append(os.path.join(la, "Programs"))
        found = []
        for root in roots:
            try:
                names = os.listdir(root)
            except OSError:
                continue
            for name in names:
                if not self._kw_score(name, keywords):
                    continue
                exe = self._find_exe_in(os.path.join(root, name), keywords)
                if exe:
                    found.append(exe)
        return found

    def _find_exe_in(self, directory: str, keywords: list, depth: int = 0) -> str:
        """在目录中递归找主程序 exe (优先文件名含关键词, 排除卸载器, 限深 3 层)"""
        try:
            entries = os.listdir(directory)
        except OSError:
            return ""
        exes = sorted(e for e in entries if e.lower().endswith(".exe"))
        for e in exes:  # 第一优先: 文件名含关键词
            if self._kw_score(e, keywords):
                return os.path.join(directory, e)
        for e in exes:  # 第二优先: 任意主程序 (排除安装器/卸载器)
            if not self._is_installer_exe(e):
                return os.path.join(directory, e)
        if depth < 3:  # 递归深入子目录
            for e in sorted(entries):
                full = os.path.join(directory, e)
                if os.path.isdir(full) and not e.startswith("."):
                    r = self._find_exe_in(full, keywords, depth + 1)
                    if r:
                        return r
        return ""

    def _find_installed(self, keywords: list) -> list:
        """自动发现系统中已安装的串口调试工具, 返回候选可执行路径列表 (去重且存在).

        结果内存缓存 (本次运行内); 空结果不缓存, 用户新装后下次点击能立即发现.
        """
        cache_key = tuple(sorted(k.lower() for k in keywords))
        if cache_key in self._installed_cache:
            return self._installed_cache[cache_key]
        found = []
        found += self._scan_registry_uninstall(keywords)
        found += self._scan_start_menu(keywords)
        found += self._scan_common_dirs(keywords)
        seen, result = set(), []
        for p in found:
            lp = p.lower()
            if lp not in seen and os.path.exists(p):
                seen.add(lp)
                result.append(p)
        if result:
            self._installed_cache[cache_key] = result
        return result

    # ==================== 扫描 ====================
    def _scan_tools(self):
        """扫描 串口调试助手/ 目录下所有 exe (递归, 跳过隐藏/系统目录), 刷新工具列表.

        安装包工具同步检测本机是否已安装: 已装则 UI 标"✓ 已安装"而非"⚠ 安装包",
        点击启动时直接启动已装版本, 避免用户误以为软件异常.
        """
        self.tools = []
        base = self._tools_dir()
        if base.is_dir():
            for exe in sorted(self._iter_exes(base)):
                abs_path = str(exe)
                is_pkg = self._is_installer_package(abs_path)
                installed = (
                    self._find_installed(self._tool_keywords({"name": exe.stem}))
                    if is_pkg
                    else []
                )
                self.tools.append(
                    {
                        "name": exe.stem,
                        "rel": exe.relative_to(base).as_posix(),
                        "abs": abs_path,
                        "is_pkg": is_pkg,
                        "installed": installed,
                    }
                )
        self._render_tools()

    @staticmethod
    def _iter_exes(base: Path):
        """递归遍历 exe, 跳过隐藏/系统目录 (如 $RECYCLE.BIN / System Volume Information)"""
        for entry in sorted(base.iterdir(), key=lambda p: p.name.lower()):
            try:
                if entry.is_dir():
                    if entry.name.startswith(("$", ".")) or "System Volume" in entry.name:
                        continue
                    yield from SerialDebugPage._iter_exes(entry)
                elif entry.suffix.lower() == ".exe":
                    yield entry
            except PermissionError:
                continue

    # ==================== UI ====================
    def _setup_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(24, 20, 24, 20)
        root.setSpacing(16)

        title = QLabel("🔌 串口调试助手")
        title.setFont(QFont("Microsoft YaHei", 20, QFont.Weight.Bold))
        title.setStyleSheet("color: #303133; background: transparent; border: none;")
        root.addWidget(title)

        subtitle = QLabel(
            "直接调用现成串口调试工具 (SSCOM / 友善串口调试助手), 不内置收发功能 · "
            "工具请放入「串口调试助手/」目录"
        )
        subtitle.setFont(QFont("Microsoft YaHei", 10))
        subtitle.setStyleSheet("color: #909399; background: transparent; border: none;")
        root.addWidget(subtitle)

        card = QFrame()
        card.setStyleSheet(CARD_STYLE)
        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(16, 12, 16, 12)
        card_layout.setSpacing(10)

        header = QHBoxLayout()
        self.list_title = QLabel("已找到的串口调试工具")
        self.list_title.setStyleSheet(SECTION_TITLE_STYLE)
        header.addWidget(self.list_title)
        header.addStretch()
        self.refresh_btn = QPushButton("🔄 刷新")
        self.refresh_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.refresh_btn.setStyleSheet(LAUNCH_BTN_STYLE)
        self.refresh_btn.clicked.connect(self._scan_tools)
        header.addWidget(self.refresh_btn)
        card_layout.addLayout(header)

        self.tools_box = QVBoxLayout()
        self.tools_box.setSpacing(8)
        card_layout.addLayout(self.tools_box)
        root.addWidget(card, 1)

    def _render_tools(self):
        """渲染工具卡片列表 (清空重建)"""
        while self.tools_box.count():
            item = self.tools_box.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()

        if not self.tools:
            hint = QLabel(
                "未找到串口调试工具\n\n"
                "请将 sscom 等串口助手 exe 放入「串口调试助手/」目录后点击「🔄 刷新」。"
            )
            hint.setStyleSheet(
                "color: #909399; font-size: 13px; padding: 24px;"
                "background: transparent; border: none;"
            )
            hint.setAlignment(Qt.AlignmentFlag.AlignCenter)
            self.tools_box.addWidget(hint)
            self.list_title.setText("已找到的串口调试工具 (0)")
            return

        self.list_title.setText(f"已找到的串口调试工具 ({len(self.tools)})")
        for tool in self.tools:
            self.tools_box.addWidget(self._tool_row(tool))
        self.tools_box.addStretch()

    def _tool_row(self, tool: dict) -> QFrame:
        row = QFrame()
        row.setStyleSheet("QFrame { background: #F5F7FA; border-radius: 8px; }")
        layout = QHBoxLayout(row)
        layout.setContentsMargins(14, 8, 10, 8)
        layout.setSpacing(12)

        name_label = QLabel(tool["name"])
        name_label.setFont(QFont("Microsoft YaHei", 12, QFont.Weight.Bold))
        name_label.setStyleSheet("color: #303133; background: transparent; border: none;")
        layout.addWidget(name_label)

        if tool.get("is_pkg"):
            installed = tool.get("installed") or []
            if installed:
                pkg_badge = QLabel("✓ 已安装")
                pkg_badge.setStyleSheet(
                    "color: #67C23A; background: #F0F9EB; border: 1px solid #67C23A;"
                    "border-radius: 4px; padding: 2px 8px; font-size: 12px;"
                )
                pkg_badge.setToolTip(
                    f"本机已安装版本:\n{installed[0]}\n\n"
                    "点击「启动」将直接启动已安装版本 (不会运行安装程序)。"
                )
            else:
                pkg_badge = QLabel("⚠ 安装包")
                pkg_badge.setStyleSheet(
                    "color: #E6A23C; background: #FDF6EC; border: 1px solid #E6A23C;"
                    "border-radius: 4px; padding: 2px 8px; font-size: 12px;"
                )
                pkg_badge.setToolTip(
                    "该程序是官方安装包 (此工具无绿色版)。\n"
                    "本机未检测到已安装版本，点击「启动」会询问是否运行安装程序。"
                )
            layout.addWidget(pkg_badge)

        path_label = QLabel(tool["rel"])
        path_label.setStyleSheet(
            "color: #909399; font-size: 12px; background: transparent; border: none;"
        )
        layout.addWidget(path_label)
        layout.addStretch()

        launch_btn = QPushButton("🚀 启动")
        launch_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        launch_btn.setStyleSheet(LAUNCH_BTN_STYLE)
        launch_btn.clicked.connect(lambda checked, t=tool: self._launch_tool(t))
        layout.addWidget(launch_btn)
        return row

    # ==================== 启动 ====================
    def _launch_tool(self, tool: dict):
        """启动外部串口调试工具; 实为安装包的 exe 优先启动系统中已安装的版本 (零弹窗)"""
        path = (tool or {}).get("abs", "")
        if not path or not os.path.isfile(path):
            QMessageBox.warning(
                self,
                "启动失败",
                f"❌ 找不到工具:\n{path or '(未解析)'}\n\n"
                f"请确认工具已放入「{self._tools_dir()}」目录。",
            )
            return
        # 绿色版 (非安装包) → 直接启动
        if not tool.get("is_pkg"):
            self._start_process(path)
            return
        # 安装包: 优先自动发现已安装版本 (注册表/开始菜单/安装目录), 找到就直接启动
        installed = tool.get("installed") or self._find_installed(self._tool_keywords(tool))
        if installed:
            self._start_process(installed[0])
            return
        # 未检测到已安装 → 询问是否运行安装程序 (默认 Yes, 与烧录软件页一致)
        ret = QMessageBox.question(
            self,
            "软件为安装包",
            f"「{tool.get('name', '')}」自带的程序是安装包:\n{path}\n\n"
            "电脑上未检测到已安装版本。\n是否现在运行安装程序?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.Yes,
        )
        if ret == QMessageBox.StandardButton.Yes:
            self._start_process(path)

    def _start_process(self, path: str):
        """启动外部程序 (Popen, 独立于本工具运行)"""
        try:
            subprocess.Popen([path], cwd=os.path.dirname(path) or None)
        except OSError as exc:
            QMessageBox.warning(self, "启动失败", f"❌ 无法启动:\n{path}\n\n{exc}")

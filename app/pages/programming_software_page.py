"""
烧录软件速查页面

功能:
- 一个芯片可配置多个烧录器 (如兆易创新 → XW16Pro Standalone Programmer / FT200 / GD32 All-In-One Programmer)
- 选择芯片厂商后再选择具体烧录器, 点击「🚀 启动烧录软件」一键唤起其可执行程序
- 速查各芯片厂商 (中微爱芯/十速/兆易创新/赛元…) 的官方烧录软件、硬件工具与使用步骤
- 配置存于 config.json → programming_software.chips.<芯片>.programmers[], 每个烧录器可单独选择 exe 并保存
- 配合「文本润色 → 烧录指导」使用, 便于产线人员快速找到对应软件
"""

import ctypes
import json
import os
import re
import shutil
import subprocess
import threading
import time
import winreg
from ctypes import wintypes
from pathlib import Path
from typing import Optional

from PyQt6.QtCore import Qt, QTimer, QUrl, pyqtSignal
from PyQt6.QtGui import QDesktopServices, QFont, QPixmap
from PyQt6.QtWidgets import (
    QButtonGroup, QCheckBox, QComboBox, QFileDialog, QFrame, QHBoxLayout, QLabel,
    QMessageBox, QPushButton, QTextBrowser, QVBoxLayout, QWidget,
)

from app.core.config_manager import ConfigManager, app_root

CARD_STYLE = (
    "background: white; border: 1px solid #E4E7ED;"
    "border-radius: 10px;"
)
SECTION_TITLE_STYLE = (
    "font-size: 14px; font-weight: bold; color: #303133;"
    "background: transparent; border: none;"
)
COMBO_STYLE = (
    "QComboBox { border: 1px solid #DCDFE6; border-radius: 6px;"
    "padding: 5px 10px; background: white; min-height: 26px; }"
    "QComboBox:focus { border-color: #409EFF; }"
    "QComboBox::drop-down { border: none; width: 24px; }"
)
LAUNCH_BTN_STYLE = (
    "QPushButton { background: #409EFF; color: white; border: none;"
    "border-radius: 8px; padding: 8px 24px; font-weight: bold; font-size: 13px; }"
    "QPushButton:hover { background: #66B1FF; }"
    "QPushButton:pressed { background: #337ECC; }"
)
# 官网按钮: 白底主色描边 (次要操作), hover 浅蓝底, 未配置时禁用
WEBSITE_BTN_STYLE = (
    "QPushButton { background: white; color: #409EFF; border: 1px solid #409EFF;"
    "border-radius: 8px; padding: 8px 20px; font-weight: bold; font-size: 13px; }"
    "QPushButton:hover { background: #ECF5FF; }"
    "QPushButton:pressed { background: #D9ECFF; }"
    "QPushButton:disabled { color: #C0C4CC; border-color: #DCDFE6; background: white; }"
)
# 厂商平铺 tab 按钮: 未选中白底灰字, 选中浅蓝底主色字, hover 微反馈
CHIP_TAB_STYLE = (
    "QPushButton { border: 1px solid #DCDFE6; border-radius: 8px;"
    "padding: 6px 20px; background: white; color: #606266;"
    "font-size: 13px; }"
    "QPushButton:hover { border-color: #409EFF; color: #409EFF; background: #F5F7FA; }"
    "QPushButton:checked { background: #ECF5FF; border-color: #409EFF;"
    "color: #409EFF; font-weight: bold; }"
)


# 烧录按钮自动识别的默认关键词 (可被各烧录器配置 auto_burn_keywords 覆盖)
DEFAULT_BURN_KEYWORDS = ("烧录", "开始", "编程", "Program", "Start")


def _find_top_window_by_pid(pid: int):
    """按 PID 查找第一个可见且有标题的顶层窗口, 返回句柄或 None (Windows)"""
    user32 = ctypes.windll.user32
    GetWindowThreadProcessId = user32.GetWindowThreadProcessId
    IsWindowVisible = user32.IsWindowVisible
    GetWindowTextLengthW = user32.GetWindowTextLengthW
    found = []

    @ctypes.WINFUNCTYPE(ctypes.c_bool, wintypes.HWND, wintypes.LPARAM)
    def _enum_proc(hwnd, lparam):
        wpid = wintypes.DWORD()
        GetWindowThreadProcessId(hwnd, ctypes.byref(wpid))
        if (
            wpid.value == pid
            and IsWindowVisible(hwnd)
            and GetWindowTextLengthW(hwnd) > 0
        ):
            found.append(hwnd)
            return False  # 找到即停止
        return True

    user32.EnumWindows(_enum_proc, 0)
    return found[0] if found else None


def _activate_window(hwnd):
    """将窗口恢复并置前 (ShowWindow + AttachThreadInput + SetForegroundWindow)"""
    user32 = ctypes.windll.user32
    kernel32 = ctypes.windll.kernel32
    ShowWindow = user32.ShowWindow
    SetForegroundWindow = user32.SetForegroundWindow
    GetCurrentThreadId = kernel32.GetCurrentThreadId
    AttachThreadInput = user32.AttachThreadInput
    GetWindowThreadProcessId = user32.GetWindowThreadProcessId

    ShowWindow(hwnd, 9)  # SW_RESTORE
    # 附加线程输入可提高 SetForegroundWindow 的成功率
    target_tid = wintypes.DWORD()
    GetWindowThreadProcessId(hwnd, ctypes.byref(target_tid))
    current_tid = GetCurrentThreadId()
    AttachThreadInput(current_tid, target_tid.value, True)
    SetForegroundWindow(hwnd)
    AttachThreadInput(current_tid, target_tid.value, False)


def _activate_process_window(pid: int, timeout_ms: int = 20000):
    """后台线程: 轮询等待指定 PID 的顶层窗口出现并将其置前 (Windows)"""
    deadline = time.monotonic() + timeout_ms / 1000.0
    while time.monotonic() < deadline:
        hwnd = _find_top_window_by_pid(pid)
        if hwnd is not None:
            _activate_window(hwnd)
            return
        time.sleep(0.2)


def _find_button_by_keywords(root_hwnd, keywords: tuple):
    """深度优先枚举子控件, 返回第一个文字含关键词的标准按钮 (hwnd, text), 无则 None"""
    user32 = ctypes.windll.user32
    result = []

    @ctypes.WINFUNCTYPE(ctypes.c_bool, wintypes.HWND, wintypes.LPARAM)
    def _enum_proc(hwnd, lparam):
        cls_buf = ctypes.create_unicode_buffer(64)
        user32.GetClassNameW(hwnd, cls_buf, 64)
        if "Button" not in cls_buf.value:
            return True
        txt_buf = ctypes.create_unicode_buffer(256)
        length = user32.GetWindowTextW(hwnd, txt_buf, 256)
        if length <= 0:
            return True
        text = txt_buf.value
        if any(kw in text for kw in keywords):
            result.append((hwnd, text))
            return False  # 找到即停止
        return True

    user32.EnumChildWindows(root_hwnd, _enum_proc, 0)
    return result[0] if result else None


def _click_button_center(hwnd):
    """物理级鼠标点击按钮中心 (对标准/自绘控件均有效)"""
    user32 = ctypes.windll.user32
    rect = wintypes.RECT()
    user32.GetWindowRect(hwnd, ctypes.byref(rect))
    cx = (rect.left + rect.right) // 2
    cy = (rect.top + rect.bottom) // 2
    user32.SetCursorPos(cx, cy)
    time.sleep(0.15)
    user32.mouse_event(0x0002, 0, 0, 0, 0)  # MOUSEEVENTF_LEFTDOWN
    user32.mouse_event(0x0004, 0, 0, 0, 0)  # MOUSEEVENTF_LEFTUP


class ProgrammingSoftwarePage(QWidget):
    """烧录软件速查页面"""

    detection_done = pyqtSignal(str, str)  # (name, 检测结果文本), 后台线程检测完本机安装后发出

    def __init__(self, parent=None):
        super().__init__(parent)
        self.cfg = ConfigManager(str(app_root() / "config.json"))
        self._updating = False  # 防止下拉框联动时重复渲染
        self._pixmap_cache: dict = {}  # image 路径 -> QPixmap, 避免反复读盘
        self._current_pixmaps: list = []  # 当前烧录器图片列表 (供窗口缩放时重绘)
        self._current_image_paths: list = []  # 当前烧录器图片路径 (tooltip 用)
        self._installed_cache: dict = {}  # 关键词组 -> 已安装候选路径列表 (启动时从记忆文件恢复, 见 _load_installed_memory)
        self._package_cache: dict = {}  # exe 路径 -> 是否安装包, 避免反复读文件头
        self._detection_pending: set = set()  # 正在后台检测的烧录器名, 防止重复起线程
        self._closed = False  # 窗口关闭后不再回填检测结果 (后台线程 emit 前检查)
        self.detection_done.connect(self._on_detection_done)
        self._load_installed_memory()  # 从磁盘记忆文件恢复, 避免每次打开都重扫系统
        self._setup_ui()

    def closeEvent(self, event):
        """窗口关闭: 标记关闭, 让仍在后台的检测线程安全退出 (不 emit 到已销毁对象)"""
        self._closed = True
        super().closeEvent(event)

    # ==================== 配置加载 ====================
    @staticmethod
    def _project_root() -> Path:
        """应用根目录 (config.json 所在目录; 打包后为 exe 所在目录)"""
        return app_root()

    def _to_stored_path(self, path: str) -> str:
        """若 exe 位于项目目录内, 转存为相对路径 (移动整个项目文件夹后依然有效)"""
        try:
            rel = Path(path).resolve().relative_to(self._project_root())
            return rel.as_posix()  # 统一正斜杠, 便于 JSON 存储与跨平台
        except (ValueError, OSError):
            return path

    def _load_chips(self) -> dict:
        """读取 config.json → programming_software.chips, 缺失时回退出厂默认"""
        chips = self.cfg.get_value("programming_software.chips", None)
        if not isinstance(chips, dict) or not chips:
            chips = (
                self.cfg.get_factory_defaults()
                .get("programming_software", {})
                .get("chips", {})
            )
        return chips or {}

    def _migrate_chips_structure(self):
        """一次性迁移:
        1) 旧版平铺字段 (software/exe/desc/…) → programmers 列表
        2) 项目目录内的绝对 exe 路径 → 相对路径 (文件夹移动后依然有效)
        """
        chips_cfg = self.cfg.config.get("programming_software", {}).get("chips", {})
        if not isinstance(chips_cfg, dict):
            return
        changed = False
        for info in chips_cfg.values():
            if not isinstance(info, dict):
                continue
            programmers = info.get("programmers")
            if not isinstance(programmers, list) or not programmers:
                # 旧版平铺结构 → programmers
                prog = {"name": info.get("software", "") or "烧录器"}
                for key in ("exe", "desc", "hardware", "usage", "note"):
                    if info.get(key):
                        prog[key] = info[key]
                info["programmers"] = [prog] if any(prog.values()) else []
                changed = True
            for prog in info.get("programmers", []):
                if not isinstance(prog, dict):
                    continue
                exe = prog.get("exe", "")
                if not exe or not os.path.isabs(exe):
                    continue
                rel = self._to_stored_path(exe)
                if rel != exe:
                    prog["exe"] = rel
                    changed = True
        if changed:
            self.cfg.save_config()
            self.chips = self._load_chips()

    def current_chip(self) -> str:
        """当前选中的芯片厂商名 (平铺 tab 按钮组)"""
        for btn, name in self._chip_map:
            if btn.isChecked():
                return name
        return ""

    def _current_programmers(self, chip: str = "") -> list:
        """当前芯片的烧录器列表 (programmers)"""
        chip = chip or self.current_chip()
        info = self.chips.get(chip, {})
        programmers = info.get("programmers", []) if isinstance(info, dict) else []
        if not isinstance(programmers, list):
            programmers = []
        return programmers

    def _current_programmer(self) -> Optional[dict]:
        """当前选中的烧录器配置, 无配置时返回 None"""
        programmers = self._current_programmers()
        if not programmers:
            return None
        idx = self.programmer_combo.currentIndex()
        if 0 <= idx < len(programmers):
            return programmers[idx]
        return programmers[0]

    # ==================== UI 构建 ====================
    def _setup_ui(self):
        self.chips = self._load_chips()
        self._migrate_chips_structure()

        root = QVBoxLayout(self)
        root.setContentsMargins(24, 20, 24, 20)
        root.setSpacing(16)

        # 标题区
        title = QLabel("💾 烧录软件")
        title.setFont(QFont("Microsoft YaHei", 20, QFont.Weight.Bold))
        root.addWidget(title)
        subtitle = QLabel(
            "各芯片厂商官方烧录软件与工具速查 · 内容可在 config.json → programming_software 中维护"
        )
        subtitle.setFont(QFont("Microsoft YaHei", 10))
        subtitle.setStyleSheet("color: #909399; background: transparent; border: none;")
        root.addWidget(subtitle)

        # 芯片选择卡片: 厂商平铺 tab + 烧录器下拉
        chip_card = QFrame()
        chip_card.setStyleSheet(CARD_STYLE)
        chip_layout = QVBoxLayout(chip_card)
        chip_layout.setContentsMargins(16, 12, 16, 12)
        chip_layout.setSpacing(10)

        chip_title = QLabel("选择芯片厂商")
        chip_title.setStyleSheet(SECTION_TITLE_STYLE)
        chip_layout.addWidget(chip_title)

        # 厂商平铺 tab 按钮组 (主分类数量少、名称短 → 平铺更直观)
        self._chip_map = []
        self.chip_group = QButtonGroup(self)
        self.chip_group.setExclusive(True)
        chip_tabs = QHBoxLayout()
        chip_tabs.setSpacing(8)
        chip_names = list(self.chips.keys())
        for i, name in enumerate(chip_names):
            btn = QPushButton(name)
            btn.setCheckable(True)
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            btn.setStyleSheet(CHIP_TAB_STYLE)
            if i == 0:
                btn.setChecked(True)
            self.chip_group.addButton(btn)
            self._chip_map.append((btn, name))
            btn.clicked.connect(lambda checked, n=name: self._update_detail(n))
            chip_tabs.addWidget(btn)
        chip_tabs.addStretch()
        chip_layout.addLayout(chip_tabs)

        # 烧录器选择行 (名称长、数量动态增减 → 下拉更合适)
        prog_row = QHBoxLayout()
        prog_row.setSpacing(10)
        prog_label = QLabel("选择烧录器/软件")
        prog_label.setStyleSheet(
            "font-size: 13px; color: #606266; background: transparent; border: none;"
        )
        prog_row.addWidget(prog_label)
        self.programmer_combo = QComboBox()
        self.programmer_combo.setFont(QFont("Microsoft YaHei", 11))
        self.programmer_combo.setMinimumWidth(280)
        self.programmer_combo.setStyleSheet(COMBO_STYLE)
        self.programmer_combo.currentTextChanged.connect(self._on_programmer_changed)
        prog_row.addWidget(self.programmer_combo)
        prog_row.addStretch()
        chip_layout.addLayout(prog_row)
        root.addWidget(chip_card)

        # 详情卡片
        detail_card = QFrame()
        detail_card.setStyleSheet(CARD_STYLE)
        detail_layout = QVBoxLayout(detail_card)
        detail_layout.setContentsMargins(16, 12, 16, 12)
        detail_layout.setSpacing(10)

        detail_header = QHBoxLayout()
        detail_title = QLabel("烧录软件信息")
        detail_title.setStyleSheet(SECTION_TITLE_STYLE)
        detail_header.addWidget(detail_title)
        detail_header.addStretch()
        self.website_btn = QPushButton("🌐 官网")
        self.website_btn.setMinimumHeight(38)
        self.website_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.website_btn.setStyleSheet(WEBSITE_BTN_STYLE)
        self.website_btn.setEnabled(False)
        self.website_btn.clicked.connect(self._open_website)
        detail_header.addWidget(self.website_btn)
        self.launch_btn = QPushButton("🚀 启动烧录软件")
        self.launch_btn.setMinimumHeight(38)
        self.launch_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.launch_btn.setStyleSheet(LAUNCH_BTN_STYLE)
        self.launch_btn.clicked.connect(self._launch)
        detail_header.addWidget(self.launch_btn)
        detail_layout.addLayout(detail_header)

        # 详情主体: 左侧烧录器硬件图 + 右侧文本
        detail_body = QHBoxLayout()
        detail_body.setSpacing(14)

        # 烧录器图片区: 固定宽度, 高度随内容拉伸; 支持多张图 (如一款软件配套多款烧录器)
        self._image_container = QWidget()
        self._image_container.setFixedWidth(300)
        self._image_container.setMinimumHeight(260)
        self._image_container.setStyleSheet(
            "QWidget { border: 1px solid #E4E7ED; border-radius: 10px;"
            "background: #F5F7FA; }"
        )
        self._image_layout = QVBoxLayout(self._image_container)
        self._image_layout.setContentsMargins(8, 8, 8, 8)
        self._image_layout.setSpacing(8)
        # 占位提示 label (无图时显示), 置于第 0 位
        self.image_label = QLabel("暂无烧录器图片")
        self.image_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.image_label.setWordWrap(True)
        self.image_label.setStyleSheet(
            "QLabel { border: none; background: transparent; color: #909399; }"
        )
        self._image_layout.addWidget(self.image_label)
        detail_body.addWidget(self._image_container)

        self.detail_browser = QTextBrowser()
        self.detail_browser.setOpenExternalLinks(True)
        self.detail_browser.setFont(QFont("Microsoft YaHei", 11))
        self.detail_browser.setMinimumHeight(280)
        self.detail_browser.setStyleSheet(
            "QTextBrowser { border: 1px solid #DCDFE6; border-radius: 8px;"
            "padding: 10px; background: white; }"
            "QTextBrowser a { color: #409EFF; }"
        )
        detail_body.addWidget(self.detail_browser, 1)
        detail_layout.addLayout(detail_body, 1)
        root.addWidget(detail_card, 1)

        # 加载第一个芯片
        if self._chip_map:
            self._update_detail(self._chip_map[0][1])

    # ==================== 详情渲染 ====================
    def _update_detail(self, chip: str):
        """芯片切换: 更新烧录器下拉框并渲染当前烧录器信息"""
        programmers = self._current_programmers(chip)
        self._updating = True
        try:
            self.programmer_combo.clear()
            if programmers:
                names = [
                    p.get("name", "") or f"烧录器{i + 1}"
                    for i, p in enumerate(programmers)
                ]
                self.programmer_combo.addItems(names)
                self.programmer_combo.setEnabled(True)
            else:
                self.programmer_combo.addItem("未配置烧录器")
                self.programmer_combo.setEnabled(False)
        finally:
            self._updating = False
        self._render_detail(chip)

    def _on_programmer_changed(self, _text: str):
        """烧录器切换: 重新渲染详情"""
        if not self._updating:
            self._render_detail(self.current_chip())

    def _render_detail(self, chip: str):
        """渲染当前芯片+烧录器的信息"""
        programmers = self._current_programmers(chip)
        if not programmers:
            self.website_btn.setEnabled(False)
            self.website_btn.setToolTip("未配置官网地址: config.json → programming_software.chips")
            self.detail_browser.setMarkdown(
                f"> ⚠ 未找到「{chip}」的烧录器配置, 请检查 "
                "config.json → programming_software.chips.\n\n"
                "在页面「🚀 启动烧录软件」中选择 exe 后会自动创建烧录器条目。"
            )
            self._render_image(None)
            return
        prog = self._current_programmer() or programmers[0]
        name = prog.get("name", "") or chip
        desc = prog.get("desc", "")
        hardware = prog.get("hardware", "")
        usage = prog.get("usage", "")
        note = prog.get("note", "")
        website = prog.get("website", "")
        self.website_btn.setEnabled(bool(website))
        self.website_btn.setToolTip(website or "未配置官网地址: config.json → programming_software.chips")

        md = [f"### {name}"]
        md.append(f"**芯片:** {chip}")
        if desc:
            md.append(f"**说明:** {desc}")
        # 本机安装检测: 后台线程扫描, 完成后经信号回填, 避免阻塞界面
        self._current_detail_name = name
        keywords = self._search_keywords(prog)
        md.append("**本机软件:** 🔍 正在检测…")
        if hardware:
            md.append(f"**硬件工具:** {hardware}")
        if usage:
            md.append("**使用步骤:**\n\n" + usage)
        if note:
            md.append("---\n**注意事项:**\n\n" + note)
        self.detail_browser.setMarkdown("\n\n".join(md))
        self._render_image(prog)
        if name not in self._detection_pending:
            self._detection_pending.add(name)
            threading.Thread(
                target=self._detect_installed_in_background,
                args=(name, keywords, self._current_exe_candidates()),
                daemon=True,
            ).start()

    def _detect_installed_in_background(self, name: str, keywords: list, candidates: list):
        """后台检测该烧录软件是否可用, 结果经 detection_done 信号回主线程

        优先判定绿色版 (配置的 exe 存在且非安装包); 绿色版不可用时再扫描已安装版本.
        注意: 附带的"绿色版"可能是安装包 (Inno/NSIS), 不能算"可用", 避免误导用户.
        """
        try:
            text = ""
            installer_path = ""
            for c in candidates:
                p = self._resolve_exe(c)
                if not p:
                    continue
                if self._is_installer_package(p):
                    installer_path = p
                else:
                    text = f"✅ 绿色版可用: `{p}`"
                    break
            if not text:
                paths = self._find_installed(keywords) if keywords else []
                if not paths:
                    if installer_path:
                        text = "⚠ 自带的程序是安装包, 未检测到已安装版本 (可点击启动运行安装向导)"
                    else:
                        text = "⚠ 未检测到本软件 (未发现绿色版, 也未扫描到已安装版本; 可点击启动或手动选择软件)"
                else:
                    shown = paths[0]
                    extra = f" (+{len(paths) - 1} 个候选)" if len(paths) > 1 else ""
                    text = f"✅ 已检测到安装: `{shown}`{extra}"
        finally:
            self._detection_pending.discard(name)
        if not self._closed:
            self.detection_done.emit(name, text)

    def _on_detection_done(self, name: str, text: str):
        """检测完成: 若详情仍显示该烧录器, 回填检测结果行"""
        if getattr(self, "_current_detail_name", "") != name:
            return  # 用户已切换到其他烧录器
        md = self.detail_browser.toMarkdown()
        md = md.replace("**本机软件:** 🔍 正在检测…", f"**本机软件:** {text}")
        self.detail_browser.setMarkdown(md)

    # ==================== 烧录器图片 ====================
    def _image_paths(self, prog: Optional[dict]) -> list:
        """解析 image 配置为图片路径列表.
        image 支持字符串(单图)或数组(多图, 如一款软件配套多款烧录器), 空串跳过.
        """
        image = (prog or {}).get("image", "") if prog else ""
        if not image:
            return []
        raw_list = image if isinstance(image, (list, tuple)) else [image]
        paths = []
        for item in raw_list:
            if not item:
                continue
            path = self._resolve_image(item)
            if path:
                paths.append(path)
        return paths

    def _resolve_image(self, image: str) -> str:
        """解析 image 配置为真实图片路径, 依次尝试:
        原样路径 → 相对项目根 → assets/programmers 目录 → 空串
        """
        expanded = os.path.expandvars(os.path.expanduser(image))
        if os.path.isfile(expanded):
            return os.path.abspath(expanded)
        if not os.path.isabs(expanded):
            rooted = self._project_root() / expanded
            if os.path.isfile(rooted):
                return str(rooted)
            # 兼容: 未带前缀时, 自动在烧录器图片目录 assets/programmers 下查找
            in_assets = self._project_root() / "assets" / "programmers" / expanded
            if os.path.isfile(in_assets):
                return str(in_assets)
        return ""

    def _render_image(self, prog: Optional[dict]):
        """按 image 配置加载并显示烧录器图片(支持多张), 缺失时显示占位提示"""
        # 清空上次的图片 label (保留第 0 位占位 label);
        # takeAt 仅从布局移除, widget 仍挂在容器上 paint — 必须 setParent(None) 立即脱离
        while self._image_layout.count() > 1:
            item = self._image_layout.takeAt(1)
            widget = item.widget() if item else None
            if widget is not None:
                widget.hide()
                widget.setParent(None)
                widget.deleteLater()

        paths = self._image_paths(prog)
        pixmaps = []
        for path in paths:
            pix = self._pixmap_cache.get(path)
            if pix is None:
                pix = QPixmap(path)
                if not pix.isNull():
                    self._pixmap_cache[path] = pix
            if pix is not None and not pix.isNull():
                pixmaps.append(pix)
                label = QLabel()
                label.setAlignment(Qt.AlignmentFlag.AlignCenter)
                label.setStyleSheet("QLabel { border: none; background: transparent; }")
                label.setToolTip(
                    f"烧录器图片: {os.path.basename(path)}\n"
                    "图片随项目文件夹移动后依然有效 (相对路径)"
                )
                self._image_layout.addWidget(label)

        if pixmaps:
            self.image_label.hide()
            self._current_pixmaps = pixmaps
            self._current_image_paths = paths
            self._apply_pixmaps()
        else:
            # 无图/加载失败 → 占位提示
            self._current_pixmaps = []
            self._current_image_paths = []
            self.image_label.show()
            self.image_label.setText("暂无烧录器图片\n\n在 config.json → programming_software\n"
                                     "chips.<芯片>.programmers[].image 中配置\n"
                                     "图片相对路径, 放置于 assets/programmers/")
            self.image_label.setToolTip("例如: image: \"assets/programmers/sc_link.png\"")

    def _apply_pixmaps(self):
        """按图片区尺寸等比缩放并显示所有烧录器图片"""
        if not self._current_pixmaps:
            return
        count = len(self._current_pixmaps)
        avail_w = max(self._image_container.width() - 16, 60)
        avail_h = self._image_container.height() - 16 - 8 * (count - 1)
        # 多图时每张图平分高度, 上限 220 防止大图撑爆
        max_h = max(avail_h // count, 90)
        max_h = min(max_h, 220)
        for i, pix in enumerate(self._current_pixmaps):
            item = self._image_layout.itemAt(i + 1)  # 0 位是占位 label
            label = item.widget() if item else None
            if label is None:
                continue
            scaled = pix.scaled(
                avail_w, max_h,
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation,
            )
            label.setPixmap(scaled)

    def resizeEvent(self, event):
        """窗口缩放时重新按尺寸渲染图片, 保持清晰不拉伸"""
        super().resizeEvent(event)
        if self._current_pixmaps:
            self._apply_pixmaps()

    # ==================== 官网 / 启动 ====================
    def _open_website(self):
        """打开当前烧录器配置的官网 (默认浏览器)"""
        prog = self._current_programmer()
        url = (prog or {}).get("website", "")
        if url:
            QDesktopServices.openUrl(QUrl(url))

    # ==================== 已安装软件自动发现 ====================
    @staticmethod
    def _search_keywords(prog: Optional[dict]) -> list:
        """当前烧录器配置的搜索关键词 (用于匹配已安装软件名)"""
        if not prog:
            return []
        kws = prog.get("search_keywords", []) or []
        if isinstance(kws, str):
            kws = [kws]
        return [k.strip() for k in kws if isinstance(k, str) and k.strip()]

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
                            score = self._kw_score(display, keywords)
                            if not score:
                                continue
                            exe = ""
                            icon = self._reg_value(sub, "DisplayIcon")
                            if icon:
                                exe = icon.split(",")[0].strip().strip('"')
                            if self._is_installer_exe(exe):
                                # DisplayIcon 常指向卸载/安装器, 从安装目录找主程序, 找不到则跳过
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
                                found.append((score, exe))
                    except OSError:
                        continue
            finally:
                winreg.CloseKey(uninstall_key)
        return [p for _, p in sorted(found, key=lambda x: -x[0])]

    @staticmethod
    def _is_installer_exe(path: str) -> bool:
        """判断是否是卸载/安装器 exe (这类程序不应作为主程序启动)"""
        name = os.path.basename(path).lower()
        return "uninst" in name or "setup" in name or "installer" in name or "卸载" in name

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

    def _is_installer_package(self, path: str) -> bool:
        """判断 exe 是否实为安装包 (Inno/NSIS/InstallShield/SFX 等), 结果缓存

        安装包 exe 双击会进入安装向导, 不能作为"绿色版"直接使用;
        启动/检测时若识别为安装包, 应优先启动已安装版本.
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

    def _scan_start_menu(self, keywords: list) -> list:
        """扫描开始菜单快捷方式, 返回匹配关键词的 .lnk 路径列表 (按匹配得分排序)"""
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
                    score = self._kw_score(f, keywords)
                    if score:
                        found.append((score, os.path.join(dirpath, f)))
        return [p for _, p in sorted(found, key=lambda x: -x[0])]

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
        # 第一优先: 文件名含关键词
        for e in exes:
            if self._kw_score(e, keywords):
                return os.path.join(directory, e)
        # 第二优先: 任意主程序 (排除安装器/卸载器)
        for e in exes:
            if not self._is_installer_exe(e):
                return os.path.join(directory, e)
        # 递归深入子目录
        if depth < 3:
            for e in sorted(entries):
                full = os.path.join(directory, e)
                if os.path.isdir(full) and not e.startswith("."):
                    exe = self._find_exe_in(full, keywords, depth + 1)
                    if exe:
                        return exe
        return ""

    def _installed_memory_file(self) -> Path:
        """已安装烧录软件发现结果的记忆文件 (与 config.json 同目录)

        记忆文件将扫描结果落盘, 下次启动直接读取, 不再重复扫描注册表/开始菜单/程序目录.
        """
        return self._project_root() / "installed_programs_memory.json"

    def _load_installed_memory(self):
        """启动时从记忆文件恢复已安装发现结果; 文件缺失/损坏时静默忽略 (首次启动重扫一次)"""
        path = self._installed_memory_file()
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
            for key_str, paths in (data.get("installed") or {}).items():
                if not key_str or not isinstance(paths, list):
                    continue
                key = tuple(key_str.split("|"))
                self._installed_cache[key] = [p for p in paths if isinstance(p, str) and p]
        except (OSError, ValueError, TypeError):
            pass

    def _save_installed_memory(self):
        """将当前已安装发现结果写入记忆文件 (临时文件 + os.replace 原子写, 防写一半损坏)"""
        try:
            path = Path(self._installed_memory_file())
            data = {
                "version": 1,
                "installed": {
                    "|".join(k): v for k, v in self._installed_cache.items() if k
                },
            }
            tmp = path.with_name(path.name + ".tmp")
            with open(tmp, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            os.replace(tmp, path)
        except OSError:
            pass  # 目录不可写等 → 仅本次内存缓存生效, 不影响使用

    def _find_installed(self, keywords: list, force_rescan: bool = False) -> list:
        """自动发现已安装的烧录软件, 返回候选可执行路径列表 (去重且存在).

        发现结果写入磁盘记忆文件 (installed_programs_memory.json):
        - 已装过一次 → 记忆文件记住路径, 之后每次启动直接读记忆, 不再扫描注册表/开始菜单
        - 从未安装 → 空结果不写盘, 每次重扫 (新装后第一次点启动仍能立即发现)
        - 装了又卸载 → 记忆路径失效触发重扫, 确认找不到时同步清理记忆文件
        force_rescan=True 时跳过记忆强制重新扫描 (点击启动时兜底, 保证发现新安装的软件).
        """
        cache_key = tuple(sorted(k.lower() for k in keywords))
        if not force_rescan and cache_key in self._installed_cache:
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
        if result:  # 扫到即写盘记忆, 下次启动直接命中不再重扫
            self._installed_cache[cache_key] = result
            self._save_installed_memory()
        elif force_rescan and cache_key in self._installed_cache:
            # 强制重扫后仍无 → 软件已卸载, 清理记忆避免下次启动拿到失效路径反复重扫
            del self._installed_cache[cache_key]
            self._save_installed_memory()
        return result

    # ==================== 启动烧录软件 ====================
    def _current_exe_candidates(self) -> list:
        """当前烧录器配置的可执行候选路径 (支持 ; 或换行分隔多个)"""
        prog = self._current_programmer()
        if prog is None:
            return []
        exe = prog.get("exe", "")
        if not exe:
            return []
        return [c.strip() for c in exe.replace("\n", ";").split(";") if c.strip()]

    def _resolve_exe(self, candidate: str):
        """解析候选为可执行文件路径, 依次尝试:
        原样路径 → 相对项目根 → PATH 搜索 → None
        """
        expanded = os.path.expandvars(os.path.expanduser(candidate))
        if os.path.isfile(expanded):
            return os.path.abspath(expanded)
        # 相对路径: 相对于项目根目录解析 (项目文件夹移动后依然有效)
        if not os.path.isabs(expanded):
            rooted = self._project_root() / expanded
            if os.path.isfile(rooted):
                return str(rooted)
            # 兼容旧配置: 若未带 "烧录软件/" 前缀, 尝试在该子目录中查找
            in_burn_dir = self._project_root() / "烧录软件" / expanded
            if os.path.isfile(in_burn_dir):
                return str(in_burn_dir)
        found = shutil.which(candidate)
        if found:
            return found
        found = shutil.which(expanded)
        return found

    def _launch(self):
        """点击启动: 启动当前芯片当前烧录器的软件

        优先级: 绿色版(非安装包) → 自动发现已安装软件 (注册表/开始菜单/安装目录) → 手动选择
        说明: 部分烧录器附带的"绿色版"实为安装包 (Inno/NSIS 等), 双击会进安装向导,
        此时优先启动已安装版本, 避免用户误以为又要重新安装.
        """
        chip = self.current_chip()
        prog = self._current_programmer()
        prog_name = (prog or {}).get("name", "") or "烧录器"
        candidates = self._current_exe_candidates()
        greens, installers = [], []
        for candidate in candidates:
            path = self._resolve_exe(candidate)
            if not path:
                continue
            (installers if self._is_installer_package(path) else greens).append(path)
        if greens:
            self._launch_feedback(f"⏳ 正在启动「{prog_name}」…")
            self._start_and_activate(greens[0])
            return
        # 绿色版不可用/实为安装包 → 自动发现已安装软件
        # 优先用记忆(磁盘记忆文件): 装过一次后, 以后点启动直接打开, 不再重复扫描注册表
        # 无记忆或文件已被卸载时才重新扫描 (从未装过的空结果不写盘, 新装的软件第一次点启动仍能立即发现)
        keywords = self._search_keywords(prog)
        installed = []
        if keywords:
            installed = [
                p for p in self._find_installed(keywords) if os.path.exists(p)
            ]
            if not installed:
                installed = [
                    p for p in self._find_installed(keywords, force_rescan=True)
                    if os.path.exists(p)
                ]
        if installed:
            self._launch_feedback(f"⏳ 正在启动已安装的「{prog_name}」…")
            self._start_and_activate(installed[0])
            return
        if not candidates:
            self._prompt_pick_exe(chip, f"烧录器「{prog_name}」还未配置软件路径。")
            return
        # 附带的绿色版是安装包, 且未检测到已安装 → 询问是否运行安装向导
        if installers and not greens:
            ret = QMessageBox.question(
                self,
                "软件为安装包",
                f"「{chip} · {prog_name}」自带的程序是安装包:\n{installers[0]}\n\n"
                "电脑上未检测到已安装版本。\n是否现在运行安装程序?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.Yes,
            )
            if ret == QMessageBox.StandardButton.Yes:
                self._launch_feedback(f"⏳ 正在运行安装程序…")
                self._start_and_activate(installers[0])
            return
        # 完全找不到: 单次弹窗告知并询问是否手动指定, 避免 warning+question 双重弹窗
        ret = QMessageBox.question(
            self,
            "未找到软件",
            f"❌ 找不到「{chip} · {prog_name}」的烧录软件:\n{'; '.join(candidates)}\n\n"
            "也未在电脑上检测到已安装版本。\n请确认软件已安装后再试。\n\n"
            "是否现在手动选择程序位置?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.Yes,
        )
        if ret == QMessageBox.StandardButton.Yes:
            self._pick_executable()

    def _launch_feedback(self, text: str, duration_ms: int = 2000):
        """启动时按钮即时反馈, 防止烧录软件冷启动数秒期间界面像卡死"""
        self.launch_btn.setText(text)
        self.launch_btn.setEnabled(False)
        self.launch_btn.setToolTip("正在启动烧录软件, 请稍候…")
        QTimer.singleShot(duration_ms, self._restore_launch_btn)

    def _restore_launch_btn(self):
        """恢复启动按钮为默认状态"""
        self.launch_btn.setText("🚀 启动烧录软件")
        self.launch_btn.setEnabled(True)
        self.launch_btn.setToolTip("")
        self.launch_btn.setStyleSheet(LAUNCH_BTN_STYLE)

    @staticmethod
    def _is_elevation_error(e: OSError) -> bool:
        """WinError 740 (需要提升权限): 程序需要管理员权限才能启动"""
        return getattr(e, "winerror", None) == 740 or getattr(e, "errno", None) == 740

    def _start_via_shell(self, path: str) -> bool:
        """用 ShellExecute 启动, 自动触发 UAC 提权 (适合需要管理员权限的程序)"""
        try:
            shell32 = ctypes.windll.shell32
            shell32.ShellExecuteW.argtypes = [
                wintypes.HWND, ctypes.c_wchar_p, ctypes.c_wchar_p,
                ctypes.c_wchar_p, ctypes.c_wchar_p, ctypes.c_int,
            ]
            shell32.ShellExecuteW.restype = ctypes.c_ssize_t
            res = shell32.ShellExecuteW(
                None, "open", path, None, os.path.dirname(path) or None, 1
            )
            return res > 32  # >32 表示成功; 1223 为用户取消 UAC
        except Exception:
            return False

    def _start_and_activate(self, path: str):
        """启动烧录软件 (exe 或 .lnk 快捷方式), 并在后台将其窗口置前"""
        if path.lower().endswith(".lnk"):
            # 开始菜单快捷方式: 直接启动 (由系统解析目标)
            try:
                os.startfile(path)
            except OSError as e:
                if self._is_elevation_error(e):
                    # 快捷方式目标需要管理员权限 → 交给 ShellExecute 触发 UAC
                    if self._start_via_shell(path):
                        return
                    QMessageBox.warning(
                        self,
                        "启动失败",
                        f"❌ 无法以管理员权限启动:\n{path}",
                    )
                    return
                QMessageBox.warning(
                    self,
                    "启动失败",
                    f"❌ 无法启动快捷方式:\n{path}\n\n{e}",
                )
            return
        try:
            proc = subprocess.Popen(
                [path],
                cwd=os.path.dirname(path) or None,
            )
        except OSError as e:
            if self._is_elevation_error(e):
                # WinError 740: Popen/CreateProcess 不会自动提权
                # 改用 ShellExecute 启动, 自动弹出 UAC 由用户确认
                if self._start_via_shell(path):
                    return
                QMessageBox.warning(
                    self,
                    "启动失败",
                    f"❌ 无法以管理员权限启动:\n{path}\n\n{e}",
                )
                return
            QMessageBox.warning(
                self,
                "启动失败",
                f"❌ 无法启动:\n{path}\n\n{e}",
            )
            return
        # 后台线程: 等待窗口出现并置前, 不阻塞界面
        if os.name == "nt":
            threading.Thread(
                target=_activate_process_window,
                args=(proc.pid,),
                daemon=True,
            ).start()

    def _prompt_pick_exe(self, chip: str, message: str):
        """询问是否现场选择烧录软件 exe 并保存到配置"""
        ret = QMessageBox.question(
            self,
            "配置烧录软件",
            f"{message}\n\n是否现在选择「{chip}」的烧录软件 (exe) 路径?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.Yes,
        )
        if ret == QMessageBox.StandardButton.Yes:
            self._pick_executable()

    def _pick_executable(self):
        """选择 exe 并保存到 config.json → programming_software.chips.<芯片>.programmers[]"""
        chip = self.current_chip()
        prog = self._current_programmer()
        prog_name = (prog or {}).get("name", "") or "烧录器"
        start_dir = ""
        for cand in self._current_exe_candidates():
            resolved = self._resolve_exe(cand)
            if resolved:
                start_dir = os.path.dirname(resolved)
                break
        path, _ = QFileDialog.getOpenFileName(
            self,
            f"选择「{chip} · {prog_name}」的烧录软件",
            start_dir,
            "可执行程序 (*.exe);;所有文件 (*.*)",
        )
        if not path:
            return
        # 写入配置并保存 (项目目录内自动转相对路径)
        stored = self._to_stored_path(path)
        chips_cfg = self.cfg.config.setdefault("programming_software", {}).setdefault("chips", {})
        info = chips_cfg.setdefault(chip, {})
        programmers = info.setdefault("programmers", [])
        if not isinstance(programmers, list):
            programmers = []
            info["programmers"] = programmers
        if not programmers:
            # 尚无任何烧录器配置: 自动创建一条
            programmers.append({"name": "新烧录器", "exe": "", "desc": "", "hardware": "", "usage": "", "note": ""})
        idx = self.programmer_combo.currentIndex()
        target = programmers[idx] if 0 <= idx < len(programmers) else programmers[0]
        if not isinstance(target, dict):
            target = {"name": "新烧录器"}
            programmers[idx if 0 <= idx < len(programmers) else 0] = target
        target["exe"] = stored
        self.cfg.save_config()
        # 同步内存并刷新
        self.chips = self._load_chips()
        self._update_detail(chip)
        QMessageBox.information(
            self,
            "配置已保存",
            f"✅ 已保存「{chip} · {prog_name}」烧录软件路径:\n{stored}\n\n"
            "点击「🚀 启动烧录软件」即可唤起。",
        )

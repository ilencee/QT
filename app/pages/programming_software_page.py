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
import os
import shutil
import subprocess
import threading
import time
from ctypes import wintypes
from pathlib import Path

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QFont
from PyQt6.QtWidgets import (
    QCheckBox, QComboBox, QFileDialog, QFrame, QHBoxLayout, QLabel, QMessageBox,
    QPushButton, QTextBrowser, QVBoxLayout, QWidget,
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


def _activate_process_window(pid: int, timeout_ms: int = 10000):
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

    def __init__(self, parent=None):
        super().__init__(parent)
        self.cfg = ConfigManager(str(app_root() / "config.json"))
        self._updating = False  # 防止下拉框联动时重复渲染
        self._setup_ui()

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

    def _current_programmers(self, chip: str = None) -> list:
        """当前芯片的烧录器列表 (programmers)"""
        chip = chip or self.chip_combo.currentText()
        info = self.chips.get(chip, {})
        programmers = info.get("programmers", []) if isinstance(info, dict) else []
        if not isinstance(programmers, list):
            programmers = []
        return programmers

    def _current_programmer(self) -> dict:
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

        # 芯片选择卡片
        chip_card = QFrame()
        chip_card.setStyleSheet(CARD_STYLE)
        chip_layout = QVBoxLayout(chip_card)
        chip_layout.setContentsMargins(16, 12, 16, 12)
        chip_layout.setSpacing(10)

        chip_title = QLabel("选择芯片厂商")
        chip_title.setStyleSheet(SECTION_TITLE_STYLE)
        chip_layout.addWidget(chip_title)

        chip_row = QHBoxLayout()
        chip_row.setSpacing(10)
        chip_row.addStretch()
        self.chip_combo = QComboBox()
        self.chip_combo.setFont(QFont("Microsoft YaHei", 12))
        self.chip_combo.setMinimumWidth(240)
        self.chip_combo.setStyleSheet(COMBO_STYLE)
        self.chip_combo.addItems(list(self.chips.keys()))
        self.chip_combo.currentTextChanged.connect(self._update_detail)
        chip_row.addWidget(self.chip_combo)
        chip_row.addStretch()
        chip_layout.addLayout(chip_row)

        # 烧录器选择行 (一个芯片可配置多个烧录器)
        prog_row = QHBoxLayout()
        prog_row.setSpacing(10)
        prog_row.addStretch()
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
        self.launch_btn = QPushButton("🚀 启动烧录软件")
        self.launch_btn.setMinimumHeight(38)
        self.launch_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.launch_btn.setStyleSheet(LAUNCH_BTN_STYLE)
        self.launch_btn.clicked.connect(self._launch)
        detail_header.addWidget(self.launch_btn)
        detail_layout.addLayout(detail_header)

        self.detail_browser = QTextBrowser()
        self.detail_browser.setOpenExternalLinks(True)
        self.detail_browser.setFont(QFont("Microsoft YaHei", 11))
        self.detail_browser.setMinimumHeight(280)
        self.detail_browser.setStyleSheet(
            "QTextBrowser { border: 1px solid #DCDFE6; border-radius: 8px;"
            "padding: 10px; background: white; }"
            "QTextBrowser a { color: #409EFF; }"
        )
        detail_layout.addWidget(self.detail_browser, 1)
        root.addWidget(detail_card, 1)

        # 加载第一个芯片
        if self.chip_combo.count():
            self._update_detail(self.chip_combo.currentText())

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
            self._render_detail(self.chip_combo.currentText())

    def _render_detail(self, chip: str):
        """渲染当前芯片+烧录器的信息"""
        programmers = self._current_programmers(chip)
        if not programmers:
            self.detail_browser.setMarkdown(
                f"> ⚠ 未找到「{chip}」的烧录器配置, 请检查 "
                "config.json → programming_software.chips.\n\n"
                "在页面「🚀 启动烧录软件」中选择 exe 后会自动创建烧录器条目。"
            )
            return
        prog = self._current_programmer() or programmers[0]
        name = prog.get("name", "") or chip
        desc = prog.get("desc", "")
        hardware = prog.get("hardware", "")
        usage = prog.get("usage", "")
        note = prog.get("note", "")

        md = [f"### {name}"]
        md.append(f"**芯片:** {chip}")
        if desc:
            md.append(f"**说明:** {desc}")
        if hardware:
            md.append(f"**硬件工具:** {hardware}")
        if usage:
            md.append("**使用步骤:**\n\n" + usage)
        if note:
            md.append("---\n**注意事项:**\n\n" + note)
        self.detail_browser.setMarkdown("\n\n".join(md))

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
        found = shutil.which(candidate)
        if found:
            return found
        found = shutil.which(expanded)
        return found

    def _launch(self):
        """点击启动: 启动当前芯片当前烧录器的软件 (启动后置前, 不弹提示)"""
        chip = self.chip_combo.currentText()
        prog = self._current_programmer()
        prog_name = prog.get("name", "") or "烧录器" if prog else "烧录器"
        candidates = self._current_exe_candidates()
        if not candidates:
            self._prompt_pick_exe(chip, f"烧录器「{prog_name}」还未配置软件路径。")
            return
        for candidate in candidates:
            path = self._resolve_exe(candidate)
            if path:
                self._start_and_activate(path)
                return
        QMessageBox.warning(
            self,
            "未找到软件",
            f"❌ 找不到「{chip} · {prog_name}」的烧录软件:\n{'; '.join(candidates)}\n\n"
            "可能未安装, 或未加入 PATH。请重新选择程序位置。",
        )
        self._prompt_pick_exe(chip, f"是否要为「{prog_name}」指定烧录软件路径?")

    def _start_and_activate(self, path: str):
        """启动烧录软件, 并在后台将其窗口置前"""
        try:
            proc = subprocess.Popen(
                [path],
                cwd=os.path.dirname(path) or None,
            )
        except OSError as e:
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
        chip = self.chip_combo.currentText()
        prog = self._current_programmer()
        prog_name = prog.get("name", "") or "烧录器" if prog else "烧录器"
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

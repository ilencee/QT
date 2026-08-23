"""
文本润色页面

功能:
- 将原始内容按类型润色为规范、专业的工程文档
- 支持类型: 工艺要求 / 测试流程 / 烧录指导
- 所有类型统一在主页面模板编辑区直接编写/粘贴原始内容 (模板即润色内容, 修改后点击「💾 保存模板」保存)
- 烧录指导: 模板按芯片厂商 (中微爱芯/十速/兆易创新/赛元…) 配置, 选芯片后编辑该芯片模板
  - 限制条件 (constraints) 为烧录指导全局通用, 所有芯片共用一份
  - 在线/离线烧录方式由 AI 根据原文自动判断, 不再分开配置
- 角色设定与限制条件通过「📌 限制要求」窗口维护, 保存立即生效
- 基于 DeepSeek API 后台润色, 不阻塞界面

使用说明:
- 所有类型: 在主页面模板编辑区直接编辑润色内容 (可直接粘贴/插入图片), 点击"🤖 AI 润色" → 结果在独立窗口
- 烧录指导: 先选芯片, 再编辑该芯片模板; 工艺要求 / 测试流程 直接编辑即可
- 结果以 Markdown 渲染在独立窗口, 可手动复制
"""

import base64
import copy
from pathlib import Path

from PyQt6.QtCore import QBuffer, QByteArray, QIODevice, Qt, QTimer
from PyQt6.QtGui import QFont, QImage, QTextDocument
from PyQt6.QtWidgets import (
    QApplication, QButtonGroup, QComboBox, QDialog, QFileDialog, QFrame, QHBoxLayout,
    QLabel, QLineEdit, QMessageBox, QPlainTextEdit, QPushButton, QRadioButton,
    QTabWidget, QTextBrowser, QTextEdit, QVBoxLayout, QWidget,
)

from app.core.config_manager import ConfigManager, app_root
from app.core.deepseek_client import DeepSeekThread, load_api_config, md_to_html
from app.core.tencent_docs import (
    TencentDocsClient, TencentDocsThread, build_config_backup_html,
)

# 默认文档类型顺序 (模板/限制内容来自 config_manager 出厂默认配置, 页面不再重复维护)
DEFAULT_TYPE_NAMES = ("工艺要求", "测试流程", "烧录指导")

CARD_STYLE = (
    "background: white; border: 1px solid #E4E7ED;"
    "border-radius: 10px;"
)
SECTION_TITLE_STYLE = (
    "font-size: 14px; font-weight: bold; color: #303133;"
    "background: transparent; border: none;"
)
PRIMARY_BTN_STYLE = (
    "QPushButton { background: #409EFF; color: white; border: none;"
    "border-radius: 8px; padding: 6px 20px; font-weight: bold; font-size: 13px; }"
    "QPushButton:hover { background: #66B1FF; }"
    "QPushButton:pressed { background: #337ECC; }"
    "QPushButton:disabled { background: #A0CFFF; }"
)
SECONDARY_BTN_STYLE = (
    "QPushButton { background: white; color: #606266; border: 1px solid #DCDFE6;"
    "border-radius: 8px; padding: 6px 20px; font-size: 13px; }"
    "QPushButton:hover { color: #409EFF; border-color: #409EFF; }"
)
COMBO_STYLE = (
    "QComboBox { border: 1px solid #DCDFE6; border-radius: 6px;"
    "padding: 5px 10px; background: white; min-height: 26px; }"
    "QComboBox:focus { border-color: #409EFF; }"
    "QComboBox::drop-down { border: none; width: 24px; }"
)
INPUT_STYLE = (
    "QLineEdit { border: 1px solid #DCDFE6; border-radius: 6px;"
    "padding: 6px 10px; background: white; }"
    "QLineEdit:focus { border-color: #409EFF; }"
)
EDIT_STYLE = (
    "QPlainTextEdit { border: 1px solid #DCDFE6; border-radius: 6px;"
    "padding: 6px; background: white; }"
    "QPlainTextEdit:focus { border-color: #409EFF; }"
)


def _deep_merge(base: dict, override: dict) -> dict:
    """递归合并两个 dict (override 覆盖 base), 返回新 dict"""
    base = copy.deepcopy(base)
    if not isinstance(override, dict):
        return base
    for key, value in override.items():
        if isinstance(value, dict) and isinstance(base.get(key), dict):
            base[key] = _deep_merge(base[key], value)
        else:
            base[key] = copy.deepcopy(value)
    return base


# ==================== 模板图片支持 (base64 data URI 内嵌, 随模板持久化) ====================

def _is_html_template(text: str) -> bool:
    """判断模板内容是否为富文本 HTML (含内嵌图片)"""
    return bool(text) and ("<img" in text or text.lstrip().startswith("<"))


def _set_edit_content(edit: QTextEdit, text: str):
    """模板内容写入编辑框: HTML (含内嵌图片) 用富文本, 否则纯文本"""
    if _is_html_template(text or ""):
        edit.setHtml(text)
    else:
        edit.setPlainText(text or "")


def _to_plain(text: str) -> str:
    """HTML 模板 → 纯文本 (图片位置保留 U+FFFC 占位字符)"""
    text = text or ""
    if not _is_html_template(text):
        return text.strip()
    doc = QTextDocument()
    doc.setHtml(text)
    return doc.toPlainText().strip()


def _plain_with_img_mark(text: str) -> str:
    """模板 → 纯文本, 图片以 [图片] 占位 (供 AI 输入 / 复制模板)"""
    return _to_plain(text).replace("\ufffc", " [图片] ").strip()


def _edit_save_text(edit: QTextEdit) -> str:
    """保存模板内容: 含图片时存 HTML (图片内嵌), 否则纯文本"""
    if "<img" in edit.toHtml():
        return edit.toHtml().strip()
    return edit.toPlainText().strip()


def _file_to_img_html(path: str) -> str:
    """读取本地图片文件 → <img data URI> HTML 片段; 读取失败返回空串"""
    try:
        with open(path, "rb") as f:
            data = f.read()
    except OSError:
        return ""
    if not data:
        return ""
    ext = Path(path).suffix.lower().lstrip(".") or "png"
    mime = {
        "png": "image/png",
        "jpg": "image/jpeg",
        "jpeg": "image/jpeg",
        "bmp": "image/bmp",
        "webp": "image/webp",
        "gif": "image/gif",
    }.get(ext, "image/png")
    return f'<img src="data:{mime};base64,{base64.b64encode(data).decode("ascii")}" />'


def _insert_image_from_dialog(edit: QTextEdit, parent=None):
    """选择图片文件并以 base64 data URI 内嵌到模板编辑框光标处"""
    path, _ = QFileDialog.getOpenFileName(
        parent,
        "插入图片",
        "",
        "图片文件 (*.png *.jpg *.jpeg *.bmp *.webp *.gif);;所有文件 (*)",
    )
    if not path:
        return
    html = _file_to_img_html(path)
    if html:
        edit.textCursor().insertHtml(html)


class TemplateEdit(QTextEdit):
    """模板富文本编辑框: 支持粘贴图片 (截图 / 复制的图片文件), 自动转 base64 data URI 内嵌, 可随模板保存"""

    def _insert_qimage(self, img: QImage):
        """将 QImage 以 PNG data URI 插入光标处"""
        ba = QByteArray()
        buf = QBuffer(ba)
        buf.open(QIODevice.OpenModeFlag.WriteOnly)
        img.save(buf, "PNG")
        buf.close()
        b64 = bytes(ba.toBase64()).decode("ascii")
        self.textCursor().insertHtml(f'<img src="data:image/png;base64,{b64}" />')

    def insertFromMimeData(self, source):
        # 剪贴板直接含位图 (截图 / 网页图片复制)
        if source.hasImage():
            img = source.imageData()
            if isinstance(img, QImage) and not img.isNull():
                self._insert_qimage(img)
                return
        # 剪贴板含本地图片文件 (文件管理器 Ctrl+C 复制, 腾讯文档同样支持)
        if source.hasUrls():
            for url in source.urls():
                if url.isLocalFile():
                    p = url.toLocalFile()
                    if Path(p).suffix.lower() in {
                        ".png", ".jpg", ".jpeg", ".bmp", ".webp", ".gif",
                    }:
                        html = _file_to_img_html(p)
                        if html:
                            self.textCursor().insertHtml(html)
                            return
        super().insertFromMimeData(source)


class PolishResultDialog(QDialog):
    """AI 润色结果独立窗口

    前台展示本次润色使用的模板 (角色设定 / 文档模板 / 限制条件, 可收起),
    下方 Markdown 渲染润色结果, 可一键复制结果或模板。
    """

    def __init__(self, doc_title: str, type_cfg: dict, parent=None):
        super().__init__(parent)
        self._doc_title = doc_title
        self._type_cfg = type_cfg or {}
        self.setWindowTitle(f"《{doc_title}》 - 润色结果")
        self.resize(980, 760)
        self.setMinimumSize(680, 560)
        self.setWindowFlag(Qt.WindowType.Window)
        self.setWindowModality(Qt.WindowModality.NonModal)

        root = QVBoxLayout(self)
        root.setContentsMargins(18, 14, 18, 14)
        root.setSpacing(12)

        # 头部: 文档标题 + 复制模板 + 复制结果
        header = QHBoxLayout()
        title = QLabel(f"📄 《{doc_title}》 润色结果")
        title.setFont(QFont("Microsoft YaHei", 15, QFont.Weight.Bold))
        header.addWidget(title)
        header.addStretch()
        self.copy_template_btn = QPushButton("📋 复制模板")
        self.copy_template_btn.setMinimumHeight(34)
        self.copy_template_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.copy_template_btn.setStyleSheet(SECONDARY_BTN_STYLE)
        self.copy_template_btn.clicked.connect(self._copy_template)
        header.addWidget(self.copy_template_btn)
        self.copy_btn = QPushButton("📋 复制结果")
        self.copy_btn.setMinimumHeight(34)
        self.copy_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.copy_btn.setStyleSheet(SECONDARY_BTN_STYLE)
        self.copy_btn.clicked.connect(self._copy_result)
        header.addWidget(self.copy_btn)
        root.addLayout(header)

        # 模板展示区 (前台显示本次使用的模板)
        self.template_frame = QFrame()
        self.template_frame.setStyleSheet(CARD_STYLE)
        tpl_layout = QVBoxLayout(self.template_frame)
        tpl_layout.setContentsMargins(14, 10, 14, 10)
        tpl_layout.setSpacing(8)
        tpl_header = QHBoxLayout()
        tpl_label = QLabel("📋 本次使用的模板")
        tpl_label.setStyleSheet(SECTION_TITLE_STYLE)
        tpl_header.addWidget(tpl_label)
        tpl_header.addStretch()
        self.toggle_template_btn = QPushButton("收起 ▲")
        self.toggle_template_btn.setMinimumHeight(26)
        self.toggle_template_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.toggle_template_btn.setStyleSheet(SECONDARY_BTN_STYLE)
        self.toggle_template_btn.clicked.connect(self._toggle_template)
        tpl_header.addWidget(self.toggle_template_btn)
        tpl_layout.addLayout(tpl_header)

        self.tpl_tabs = QTabWidget()
        self.tpl_tabs.setStyleSheet(
            "QTabBar::tab { padding: 6px 16px; font-size: 12px; }"
            "QTabBar::tab:selected { color: #409EFF; }"
        )
        self.tpl_tabs.addTab(
            self._make_tab(self._type_cfg.get("system_role", "")), "角色设定"
        )
        self.tpl_tabs.addTab(
            self._make_tab(self._type_cfg.get("template", "")), "文档模板"
        )
        constraints = self._type_cfg.get("constraints") or []
        if isinstance(constraints, str):
            constraints = [constraints]
        constraints_text = "\n".join(
            f"• {str(c).strip()}" for c in constraints if str(c).strip()
        )
        self.tpl_tabs.addTab(self._make_tab(constraints_text), "限制条件")
        tpl_layout.addWidget(self.tpl_tabs)
        root.addWidget(self.template_frame)

        # 结果展示区
        result_frame = QFrame()
        result_frame.setStyleSheet(CARD_STYLE)
        res_layout = QVBoxLayout(result_frame)
        res_layout.setContentsMargins(14, 10, 14, 10)
        res_layout.setSpacing(8)
        res_header = QHBoxLayout()
        res_label = QLabel("✨ 润色结果")
        res_label.setStyleSheet(SECTION_TITLE_STYLE)
        res_header.addWidget(res_label)
        res_header.addStretch()
        self.status_label = QLabel("")
        self.status_label.setStyleSheet(
            "color: #909399; background: transparent; border: none;"
        )
        res_header.addWidget(self.status_label)
        res_layout.addLayout(res_header)
        self.result_browser = QTextBrowser()
        self.result_browser.setOpenExternalLinks(True)
        self.result_browser.setFont(QFont("Microsoft YaHei", 11))
        self.result_browser.setStyleSheet(
            "QTextBrowser { border: 1px solid #DCDFE6; border-radius: 8px;"
            "padding: 10px; background: white; }"
            "QTextBrowser a { color: #409EFF; }"
        )
        res_layout.addWidget(self.result_browser, 1)
        root.addWidget(result_frame, 1)

    @staticmethod
    def _make_tab(text: str) -> QTextBrowser:
        browser = QTextBrowser()
        browser.setFont(QFont("Microsoft YaHei", 11))
        browser.setStyleSheet(
            "QTextBrowser { border: 1px solid #DCDFE6; border-radius: 8px;"
            "padding: 8px; background: #FAFAFA; }"
        )
        if _is_html_template(text):
            browser.setHtml(text)  # 模板含内嵌图片
        else:
            browser.setPlainText(text)
        return browser

    # ==================== 结果状态 ====================
    def set_loading(self, text="⏳ 正在润色, 请稍候 (约 10~30 秒)…"):
        self.status_label.setText(text)
        self.status_label.setStyleSheet(
            "color: #409EFF; background: transparent; border: none;"
        )
        self.result_browser.setPlainText("")

    def set_result(self, text: str):
        # Qt setMarkdown 不支持表格且折叠段内换行, 先经 md_to_html 转为 HTML 再渲染
        self.result_browser.setHtml(md_to_html(text))
        self._flash_status("✅ 润色完成, 可复制使用。", "#67C23A")

    def set_error(self, error: str):
        self.result_browser.setPlainText(f"❌ DeepSeek 请求失败:\n{error}")
        self._flash_status("❌ 请求失败, 请检查 API Key 与网络。", "#F56C6C")

    # ==================== 交互 ====================
    def _toggle_template(self):
        hidden = self.template_frame.isHidden()
        self.template_frame.setVisible(hidden)
        self.toggle_template_btn.setText("收起 ▲" if hidden else "展开 ▼")

    def _template_text(self) -> str:
        cfg = self._type_cfg
        parts = []
        role = (cfg.get("system_role") or "").strip()
        if role:
            parts.append("角色设定:\n" + role)
        template = _plain_with_img_mark(cfg.get("template") or "")
        if template:
            parts.append("文档模板:\n" + template)
        constraints = cfg.get("constraints") or []
        if isinstance(constraints, str):
            constraints = [constraints]
        items = [str(c).strip() for c in constraints if c and str(c).strip()]
        if items:
            parts.append("限制条件:\n- " + "\n- ".join(items))
        return f"《{self._doc_title}》 模板:\n\n" + "\n\n".join(parts)

    def _copy_template(self):
        QApplication.clipboard().setText(self._template_text())
        self._flash_status("✅ 已复制模板", "#67C23A")

    def _copy_result(self):
        text = self.result_browser.toPlainText()
        if text:
            QApplication.clipboard().setText(text)
            self._flash_status("✅ 已复制润色结果", "#67C23A")
        else:
            self._flash_status("暂无内容可复制", "#E6A23C")

    def _flash_status(self, text, color):
        self.status_label.setText(text)
        self.status_label.setStyleSheet(
            f"color: {color}; background: transparent; border: none;"
        )
        QTimer.singleShot(2500, lambda: self.status_label.setText(""))


class ConstraintsDialog(QDialog):
    """限制要求编辑窗口: 编辑当前文档类型的角色设定与全局限制条件

    保存不关闭窗口 (右上角 X 关闭, 保存反馈显示在按钮行)。烧录指导时编辑
    全局限制 + 当前芯片角色设定; 其他类型编辑该类型的角色与限制。
    模板在主页面模板编辑区直接编辑并手工保存, 不再单独配置窗口。
    """

    def __init__(self, cfg, polish_types, doc_type, chip="", parent=None):
        super().__init__(parent)
        self.cfg = cfg
        self.polish_types = polish_types
        self.doc_type = doc_type
        self.chip = chip
        suffix = f" ({chip})" if chip else ""
        self.setWindowTitle(f"📌 限制要求 - {doc_type}{suffix}")
        self.resize(640, 480)
        self.setMinimumSize(520, 400)

        root = QVBoxLayout(self)
        root.setContentsMargins(20, 16, 20, 16)
        root.setSpacing(12)

        title = QLabel(f"📌 限制要求 - {doc_type}{suffix}")
        title.setFont(QFont("Microsoft YaHei", 14, QFont.Weight.Bold))
        root.addWidget(title)
        hint = QLabel(
            "统一维护「角色设定」与「限制条件」, AI 润色时会遵循这些限制组织内容。"
            + ("烧录指导的限制条件为所有芯片共用, 角色设定仅作用于当前芯片。" if chip else "")
            + "保存后立即生效, 不会关闭窗口 (右上角 X 关闭)。"
        )
        hint.setFont(QFont("Microsoft YaHei", 10))
        hint.setStyleSheet("color: #909399; background: transparent; border: none;")
        hint.setWordWrap(True)
        root.addWidget(hint)

        role_label = QLabel("角色设定 (system_role)")
        role_label.setStyleSheet(SECTION_TITLE_STYLE)
        root.addWidget(role_label)
        self.role_edit = QLineEdit()
        self.role_edit.setFont(QFont("Microsoft YaHei", 11))
        self.role_edit.setPlaceholderText("例如: 你是一名资深电子制造工艺工程师。")
        self.role_edit.setStyleSheet(INPUT_STYLE)
        root.addWidget(self.role_edit)

        constraints_label = QLabel("限制条件 (constraints, 每行一条)")
        constraints_label.setStyleSheet(SECTION_TITLE_STYLE)
        root.addWidget(constraints_label)
        self.constraints_edit = QPlainTextEdit()
        self.constraints_edit.setFont(QFont("Microsoft YaHei", 11))
        self.constraints_edit.setPlaceholderText(
            "每行一条限制, 例如:\n条理清晰, 分条列出\n保留原文所有关键数据与约束, 不凭空增加内容"
        )
        self.constraints_edit.setStyleSheet(EDIT_STYLE)
        root.addWidget(self.constraints_edit, 1)

        btn_row = QHBoxLayout()
        btn_row.addStretch()
        self.save_status = QLabel("")
        self.save_status.setFont(QFont("Microsoft YaHei", 10))
        self.save_status.setStyleSheet("color: #67C23A; background: transparent; border: none;")
        btn_row.addWidget(self.save_status)
        cancel_btn = QPushButton("取消")
        cancel_btn.setMinimumHeight(36)
        cancel_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        cancel_btn.setStyleSheet(SECONDARY_BTN_STYLE)
        cancel_btn.clicked.connect(self.reject)
        btn_row.addWidget(cancel_btn)
        save_btn = QPushButton("保存")
        save_btn.setMinimumHeight(36)
        save_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        save_btn.setStyleSheet(PRIMARY_BTN_STYLE)
        save_btn.clicked.connect(self._save)
        btn_row.addWidget(save_btn)
        root.addLayout(btn_row)

        self._load_current()

    # ==================== 加载与保存 ====================
    def _load_current(self):
        """加载当前类型 (烧录指导: 全局限制 + 当前芯片角色) 到编辑框"""
        if self.doc_type == "烧录指导":
            cfg = self.polish_types.get("烧录指导", {}).get("chips", {}).get(self.chip, {})
            constraints = self.polish_types.get("烧录指导", {}).get("constraints", [])
        else:
            cfg = self.polish_types.get(self.doc_type, {})
            constraints = cfg.get("constraints", [])
        if not isinstance(cfg, dict):
            cfg = {}
        self.role_edit.setText(cfg.get("system_role", ""))
        if isinstance(constraints, str):
            constraints = [constraints]
        self.constraints_edit.setPlainText("\n".join(str(c) for c in constraints))

    def _save(self):
        """保存到内存配置并写回 config.json (不关闭窗口, 右上角 X 关闭)"""
        role = self.role_edit.text().strip()
        constraints = [
            line.strip()
            for line in self.constraints_edit.toPlainText().splitlines()
            if line.strip()
        ]
        cfg_types = self.cfg.config.setdefault("text_polish", {}).setdefault("types", {})
        if self.doc_type == "烧录指导":
            chip = self.chip
            if not chip:
                return
            burn = self.polish_types.setdefault("烧录指导", {})
            chip_cfg = burn.setdefault("chips", {}).setdefault(chip, {})
            if not isinstance(chip_cfg, dict):
                chip_cfg = {}
            chip_cfg["system_role"] = role
            burn["chips"][chip] = chip_cfg
            burn["constraints"] = constraints
            # 写回 config.json: 先归一化残留旧结构, 再写入当前芯片
            burn_cfg = cfg_types.setdefault("烧录指导", {})
            normalized = TextPolishPage._normalize_burn_cfg(burn_cfg)
            n_chip = normalized.setdefault("chips", {}).setdefault(chip, {})
            n_chip["system_role"] = role
            normalized["constraints"] = constraints
            cfg_types["烧录指导"] = normalized
        else:
            data = copy.deepcopy(self.polish_types.get(self.doc_type, {}))
            data["system_role"] = role
            data["constraints"] = constraints
            self.polish_types[self.doc_type] = data
            cfg_types[self.doc_type] = data
        self.cfg.save_config()
        self.save_status.setText("✅ 已保存 (右上角 X 关闭)")
        QTimer.singleShot(3500, lambda: self.save_status.setText(""))


class TextPolishPage(QWidget):
    """文本润色页面"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.cfg = ConfigManager(str(app_root() / "config.json"))
        self.polish_types = self._load_polish_types()
        self.ai_thread = None
        self.td_thread = None  # 腾讯文档备份线程
        self._result_dlg = None  # 润色结果独立窗口
        self._loaded_template_text = ""  # 当前模板最近保存点 (用于恢复与脏检查)
        self._prev_chip = ""  # 切换前芯片 (切换时确认保存后回退)
        self._prev_type = DEFAULT_TYPE_NAMES[0]  # 切换前类型 (切换时确认保存到旧类型)
        self._setup_ui()
        self._on_type_changed()  # 初始化: 加载默认文档类型的模板到编辑区

    # ==================== UI 构建 ====================
    def _setup_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(24, 20, 24, 20)
        root.setSpacing(16)

        # 标题区
        title = QLabel("✍️ 文本润色")
        title.setFont(QFont("Microsoft YaHei", 18, QFont.Weight.Bold))
        root.addWidget(title)

        # 1. 类型选择卡片
        type_card = QFrame()
        type_card.setStyleSheet(CARD_STYLE)
        type_layout = QVBoxLayout(type_card)
        type_layout.setContentsMargins(16, 10, 16, 10)
        type_layout.setSpacing(8)

        type_row = QHBoxLayout()
        type_row.setSpacing(24)
        self.type_group = QButtonGroup(self)
        for idx, text in enumerate(DEFAULT_TYPE_NAMES):
            rb = QRadioButton(text)
            rb.setFont(QFont("Microsoft YaHei", 11))
            rb.setCursor(Qt.CursorShape.PointingHandCursor)
            rb.setStyleSheet(
                "QRadioButton { color: #303133; }"
                "QRadioButton::indicator { width: 16px; height: 16px; }"
            )
            if idx == 0:
                rb.setChecked(True)
            self.type_group.addButton(rb)
            type_row.addWidget(rb)
        type_row.addStretch()
        type_layout.addLayout(type_row)

        # 芯片选择行 (仅烧录指导时可见; 在线/离线由 AI 自动判断, 不分开选择)
        chip_row = QHBoxLayout()
        chip_row.setSpacing(10)
        chip_label = QLabel("芯片厂商:")
        chip_label.setFont(QFont("Microsoft YaHei", 11))
        chip_row.addWidget(chip_label)
        self.chip_combo = QComboBox()
        self.chip_combo.setFont(QFont("Microsoft YaHei", 11))
        self.chip_combo.setMinimumWidth(180)
        self.chip_combo.setStyleSheet(COMBO_STYLE)
        chip_row.addWidget(self.chip_combo)
        chip_row.addStretch()
        self.chip_row_frame = QFrame()
        self.chip_row_frame.setLayout(chip_row)
        self.chip_row_frame.setVisible(False)
        type_layout.addWidget(self.chip_row_frame)

        root.addWidget(type_card)

        self.type_group.buttonClicked.connect(self._on_type_changed)
        self.chip_combo.currentTextChanged.connect(self._on_chip_changed)

        # 2. 模板编辑卡片 (所有类型通用, 模板可直接编辑, 修改后点「💾 保存模板」保存)
        self.template_preview_frame = QFrame()
        self.template_preview_frame.setStyleSheet(CARD_STYLE)
        tp_layout = QVBoxLayout(self.template_preview_frame)
        tp_layout.setContentsMargins(16, 10, 16, 10)
        tp_layout.setSpacing(8)
        tp_header = QHBoxLayout()
        self.template_card_title = QLabel("📝 模板即润色内容 (可直接编辑, 修改后点击『💾 保存模板』保存)")
        self.template_card_title.setStyleSheet(SECTION_TITLE_STYLE)
        tp_header.addWidget(self.template_card_title)
        tp_header.addStretch()
        self.template_img_btn = QPushButton("🖼 插入图片")
        self.template_img_btn.setMinimumHeight(28)
        self.template_img_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.template_img_btn.setStyleSheet(SECONDARY_BTN_STYLE)
        self.template_img_btn.clicked.connect(
            lambda: _insert_image_from_dialog(self.template_preview_edit, self)
        )
        tp_header.addWidget(self.template_img_btn)
        self.copy_template_btn = QPushButton("📋 复制模板")
        self.copy_template_btn.setMinimumHeight(28)
        self.copy_template_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.copy_template_btn.setStyleSheet(SECONDARY_BTN_STYLE)
        self.copy_template_btn.clicked.connect(self._copy_template_clicked)
        tp_header.addWidget(self.copy_template_btn)
        self.save_template_btn = QPushButton("💾 保存模板")
        self.save_template_btn.setMinimumHeight(28)
        self.save_template_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.save_template_btn.setStyleSheet(SECONDARY_BTN_STYLE)
        self.save_template_btn.clicked.connect(self._save_template_clicked)
        tp_header.addWidget(self.save_template_btn)
        self.template_reset_btn = QPushButton("↺ 恢复原模板")
        self.template_reset_btn.setMinimumHeight(28)
        self.template_reset_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.template_reset_btn.setStyleSheet(SECONDARY_BTN_STYLE)
        self.template_reset_btn.clicked.connect(self._restore_template)
        tp_header.addWidget(self.template_reset_btn)
        tp_layout.addLayout(tp_header)
        self.template_preview_edit = TemplateEdit()
        self.template_preview_edit.setFont(QFont("Microsoft YaHei", 11))
        self.template_preview_edit.setPlaceholderText(
            "在此直接编辑润色内容: 直接写或粘贴需要润色的原始文本, AI 将按「📌 限制要求」润色为规范文档…\n"
            "修改后点『💾 保存模板』保存; 可直接粘贴/插入图片 (示意图、工艺图等)"
        )
        self.template_preview_edit.setStyleSheet(
            "QTextEdit { border: 1px solid #DCDFE6; border-radius: 8px;"
            "padding: 8px; background: white; }"
            "QTextEdit:focus { border-color: #409EFF; }"
        )
        tp_layout.addWidget(self.template_preview_edit, 1)
        root.addWidget(self.template_preview_frame, 1)

        # 3. 操作按钮行
        btn_row = QHBoxLayout()
        btn_row.setSpacing(12)

        self.polish_btn = QPushButton("🤖 AI 润色")
        self.polish_btn.setMinimumHeight(40)
        self.polish_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.polish_btn.setStyleSheet(PRIMARY_BTN_STYLE)
        self.polish_btn.clicked.connect(self.polish)

        self.clear_btn = QPushButton("清空输入")
        self.clear_btn.setMinimumHeight(40)
        self.clear_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.clear_btn.setStyleSheet(SECONDARY_BTN_STYLE)
        self.clear_btn.clicked.connect(self._clear_input)

        self.constraints_btn = QPushButton("📌 限制要求")
        self.constraints_btn.setMinimumHeight(40)
        self.constraints_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.constraints_btn.setStyleSheet(SECONDARY_BTN_STYLE)
        self.constraints_btn.clicked.connect(self.open_constraints_dialog)

        self.td_backup_btn = QPushButton("☁ 备份到腾讯文档")
        self.td_backup_btn.setMinimumHeight(40)
        self.td_backup_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.td_backup_btn.setStyleSheet(SECONDARY_BTN_STYLE)
        self.td_backup_btn.clicked.connect(self._td_backup_templates)

        self.status_label = QLabel("")
        self.status_label.setStyleSheet("color: #909399; background: transparent; border: none;")

        btn_row.addWidget(self.polish_btn)
        btn_row.addWidget(self.clear_btn)
        btn_row.addWidget(self.constraints_btn)
        btn_row.addWidget(self.td_backup_btn)
        btn_row.addWidget(self.status_label)
        btn_row.addStretch()
        root.addLayout(btn_row)

        # 润色结果在独立窗口 (PolishResultDialog) 中展示, 页面内不再内嵌结果区

    # ==================== 模板与限制配置 ====================
    def _load_polish_types(self) -> dict:
        """从 config.json → text_polish.types 加载配置, 与出厂默认深度合并"""
        defaults = self.cfg.get_factory_defaults().get("text_polish", {}).get("types", {})
        cfg_types = self.cfg.config.get("text_polish", {}).get("types", {})
        if not isinstance(cfg_types, dict) or not cfg_types:
            return copy.deepcopy(defaults)
        types = {}
        for name in DEFAULT_TYPE_NAMES:
            if name == "烧录指导":
                types[name] = self._merge_burn_cfg(defaults.get(name, {}), cfg_types.get(name, {}))
            else:
                types[name] = _deep_merge(defaults.get(name, {}), cfg_types.get(name, {}))
        for name, item in cfg_types.items():
            if name not in types and isinstance(item, dict):
                types[name] = copy.deepcopy(item)
        return types

    @staticmethod
    def _normalize_burn_cfg(user_burn: dict) -> dict:
        """仅迁移旧版「芯片 × 烧录方式」双层结构 (不动默认):
        - 旧版: chips[芯片][在线烧录/离线烧录] = {system_role, template, constraints}
        - 新版: chips[芯片] = {system_role, template} + 全局 constraints
        迁移规则: 模式模板在线优先、离线补缺; 该芯片各模式的限制
        (厂商/模式专属要求) 去重后并入该芯片模板末尾; 顶层 modes 键删除。"""
        if not isinstance(user_burn, dict) or not user_burn:
            return copy.deepcopy(user_burn or {})
        user_burn = copy.deepcopy(user_burn)
        old_modes = ("在线烧录", "离线烧录")
        has_old = any(
            isinstance(cfg, dict) and any(m in cfg for m in old_modes)
            for cfg in user_burn.get("chips", {}).values()
        )
        if not has_old:
            user_burn.pop("modes", None)
            return user_burn
        chips = {}
        for chip, cfg in (user_burn.get("chips") or {}).items():
            if not isinstance(cfg, dict):
                continue
            if any(m in cfg for m in old_modes):
                mc_online = cfg.get("在线烧录")
                mc_offline = cfg.get("离线烧录")
                if isinstance(mc_online, dict) and isinstance(mc_offline, dict):
                    # 在线优先, 离线补充在线缺失的字段
                    merged = _deep_merge(mc_offline, mc_online)
                elif isinstance(mc_online, dict):
                    merged = copy.deepcopy(mc_online)
                elif isinstance(mc_offline, dict):
                    merged = copy.deepcopy(mc_offline)
                else:
                    merged = {}
                # 该芯片各模式的限制并入模板末尾 (厂商/模式专属要求随芯片走)
                extra = []
                for m in old_modes:
                    mc = cfg.get(m)
                    if isinstance(mc, dict):
                        cs = mc.get("constraints", [])
                        if isinstance(cs, str):
                            cs = [cs]
                        for c in cs:
                            c = str(c).strip()
                            if c and c not in extra:
                                extra.append(c)
                if extra and merged.get("template"):
                    merged["template"] = (
                        merged["template"].rstrip() + "\n\n注意事项:\n- " + "\n- ".join(extra)
                    )
                merged.pop("constraints", None)
                chips[chip] = merged
            else:
                chips[chip] = cfg
        out = {"chips": chips}
        if user_burn.get("constraints"):
            out["constraints"] = user_burn["constraints"]
        return out

    @staticmethod
    def _merge_burn_cfg(default_burn: dict, user_burn: dict) -> dict:
        """加载时合并烧录指导配置: 先迁移旧结构, 再与出厂默认深度合并"""
        if not isinstance(user_burn, dict) or not user_burn:
            return copy.deepcopy(default_burn)
        return _deep_merge(default_burn, TextPolishPage._normalize_burn_cfg(user_burn))

    def _build_system_prompt(self, type_cfg: dict, include_template: bool = False) -> str:
        """由 system_role + constraints 组装 system 提示词
        所有类型模板即润色输入 (已随原文发送), 不再重复放入 system"""
        parts = [type_cfg["system_role"]] if type_cfg.get("system_role") else []
        if include_template:
            template = (type_cfg.get("template") or "").strip()
            if template:
                parts.append("请按以下模板组织文档内容:\n" + template)
        constraints = type_cfg.get("constraints") or []
        if isinstance(constraints, str):
            constraints = [constraints]
        items = [str(c).strip() for c in constraints if c and str(c).strip()]
        if items:
            parts.append("限制条件:\n- " + "\n- ".join(items))
        return "\n\n".join(parts)

    # ==================== 选择状态 ====================
    def _selected_type(self) -> str:
        btn = self.type_group.checkedButton()
        return btn.text() if btn else DEFAULT_TYPE_NAMES[0]

    def _selected_chip(self) -> str:
        return self.chip_combo.currentText() if self.chip_combo.count() else ""

    def _on_type_changed(self, *_):
        """切换文档类型: 模板编辑区所有类型通用; 烧录指导另显示芯片行。
        模板有未保存修改时先确认 (保存到旧类型/丢弃/取消回退)。"""
        new_type = self._selected_type()
        if self._prev_type != new_type and self._template_dirty():
            ret = self._confirm_unsaved(
                "切换文档类型",
                "模板有未保存的修改, 切换前是否保存?",
                save_target=lambda: self._save_template(self._prev_type),
            )
            if ret == "cancel":
                for rb in self.type_group.buttons():
                    if rb.text() == self._prev_type:
                        rb.setChecked(True)
                        break
                return
        self._prev_type = new_type
        is_burn = new_type == "烧录指导"
        self.chip_row_frame.setVisible(is_burn)
        if is_burn:
            self._refresh_chip_combo()
        else:
            self._update_template_preview()

    def _on_chip_changed(self, *_):
        """用户手动切换芯片: 模板有未保存修改先确认 (保存到旧芯片/丢弃/取消回退)"""
        new_chip = self.chip_combo.currentText()
        if self._prev_chip and self._prev_chip != new_chip and self._template_dirty():
            ret = self._confirm_unsaved(
                "切换芯片",
                "模板有未保存的修改, 切换前是否保存?",
                save_target=lambda: self._save_template("烧录指导", chip=self._prev_chip),
            )
            if ret == "cancel":
                self.chip_combo.blockSignals(True)
                self.chip_combo.setCurrentText(self._prev_chip)
                self.chip_combo.blockSignals(False)
                return
        self._prev_chip = new_chip
        self._update_template_preview()

    def flush_pending_save(self) -> bool:
        """页面切换 / 程序退出前: 模板有未保存修改时弹确认 (保存/不保存/取消)。
        返回 False 表示用户取消, 调用方应中止切换/关闭。"""
        if not self._template_dirty():
            return True
        ret = self._confirm_unsaved(
            "未保存的修改",
            "模板有未保存的修改, 是否保存?",
            save_target=lambda: self._save_template(),
        )
        return ret != "cancel"

    def _restore_template(self):
        """恢复到最近保存的模板 (丢弃未保存的修改)"""
        _set_edit_content(self.template_preview_edit, self._loaded_template_text or "")
        self.template_preview_edit.setFocus()

    def _refresh_chip_combo(self):
        burn = self.polish_types.get("烧录指导", {})
        chips = burn.get("chips", {})
        current = self.chip_combo.currentText()
        self.chip_combo.blockSignals(True)
        self.chip_combo.clear()
        self.chip_combo.addItems(list(chips.keys()))
        if current in chips:
            self.chip_combo.setCurrentText(current)
        self.chip_combo.blockSignals(False)
        # 实际显示的芯片才是「切换前芯片」, 供 _on_chip_changed 落盘用
        self._prev_chip = self.chip_combo.currentText()
        self._update_template_preview()

    def _update_template_preview(self):
        """加载当前类型/芯片的模板到编辑区 (可直接编辑, 修改后点『💾 保存模板』保存)"""
        cfg = self._resolve_type_cfg()
        if not isinstance(cfg, dict):
            self._loaded_template_text = ""
            _set_edit_content(self.template_preview_edit, "")
            return
        self.template_card_title.setText(
            "📝 模板即润色内容 (可直接编辑, 修改后点击『💾 保存模板』保存)"
        )
        template = (cfg.get("template") or "").strip()
        self._loaded_template_text = template
        _set_edit_content(self.template_preview_edit, template)

    def _resolve_type_cfg(self):
        """解析当前选择的模板配置 (烧录指导取 芯片配置 + 全局限制条件)"""
        doc_type = self._selected_type()
        cfg = self.polish_types.get(doc_type)
        if not isinstance(cfg, dict):
            return None
        if doc_type == "烧录指导":
            chip = self._selected_chip()
            if not chip:
                return None
            chip_cfg = cfg.get("chips", {}).get(chip)
            if not isinstance(chip_cfg, dict):
                return None
            merged = copy.deepcopy(chip_cfg)
            gc = cfg.get("constraints", [])
            if isinstance(gc, str):
                gc = [gc]
            items = [str(c).strip() for c in gc if c and str(c).strip()]
            if items:
                merged["constraints"] = items
            return merged
        return cfg

    def _doc_title(self) -> str:
        """当前生成的文档标题"""
        doc_type = self._selected_type()
        if doc_type == "烧录指导":
            return f"{self._selected_chip()} 烧录指导"
        return doc_type

    # ==================== 动作 ====================
    def open_constraints_dialog(self):
        """打开限制要求窗口 (角色设定 + 限制条件, 保存不关闭窗口)"""
        # 模板有未保存修改先确认 (可先保存, 避免对话框保存时覆盖旧模板)
        if self._template_dirty():
            ret = self._confirm_unsaved(
                "打开限制要求",
                "模板有未保存的修改, 是否先保存?",
                save_target=lambda: self._save_template(),
            )
            if ret == "cancel":
                return
        doc_type = self._selected_type()
        chip = self._selected_chip() if doc_type == "烧录指导" else ""
        dlg = ConstraintsDialog(self.cfg, self.polish_types, doc_type, chip, self)
        dlg.exec()
        # 限制/角色可能已修改, 窗口关闭后重新加载以同步界面
        self.polish_types = self._load_polish_types()
        if doc_type == "烧录指导":
            self._refresh_chip_combo()
        else:
            self._update_template_preview()
        self._set_status("✅ 限制要求已保存并生效。", "#67C23A")

    # ==================== 模板保存 ====================
    def _template_dirty(self) -> bool:
        """模板编辑框内容是否相对最近保存点有未保存修改 (图片等富文本差异归一化后比较)"""
        return (
            self.template_preview_edit.toPlainText().replace("\ufffc", " [图片] ").strip()
            != _to_plain(self._loaded_template_text).replace("\ufffc", " [图片] ").strip()
        )

    def _confirm_unsaved(self, title: str, text: str, save_target) -> str:
        """模板有未保存修改时的三选确认: 保存 / 不保存 / 取消。
        返回 'save' / 'discard' / 'cancel'; 选择保存时先执行 save_target。"""
        box = QMessageBox(self)
        box.setWindowTitle(title)
        box.setText(text)
        save_btn = box.addButton("保存", QMessageBox.ButtonRole.AcceptRole)
        discard_btn = box.addButton("不保存", QMessageBox.ButtonRole.DestructiveRole)
        cancel_btn = box.addButton("取消", QMessageBox.ButtonRole.RejectRole)
        box.setDefaultButton(save_btn)
        box.exec()
        clicked = box.clickedButton()
        if clicked is discard_btn:
            return "discard"
        if clicked is cancel_btn:
            return "cancel"
        try:
            save_target()
        except Exception:
            pass
        return "save"

    def _copy_template_clicked(self):
        """📋 复制模板按钮: 直接执行原生全选 + Ctrl+C 复制。

        用 QTextEdit.copy() 走 Qt 原生剪贴板路径, 与用户手动 Ctrl+C 完全一致
        (同时写入 ODT/HTML/Markdown/纯文本, 粘贴到 Word/微信等带真实图片)。
        """
        edit = self.template_preview_edit
        if not edit.toPlainText().strip() and "<img" not in edit.toHtml():
            self._set_status("⚠ 模板为空, 无内容可复制。", "#E6A23C")
            return
        cursor = edit.textCursor()  # 保存原光标/选区
        edit.selectAll()            # 全选 → copy() 复制整个模板 (含图片)
        edit.copy()
        edit.setTextCursor(cursor)  # 恢复原光标位置
        edit.setFocus()
        self._set_status("✅ 模板已复制到剪贴板 (含图片)。", "#67C23A")

    def _save_template_clicked(self):
        """💾 保存模板按钮: 把模板编辑区当前内容手工写入内存配置与 config.json"""
        edit = self.template_preview_edit
        text = (_edit_save_text(edit) or "").strip()
        # 空内容 (无文本且无图片) 不落盘, 保护默认模板与既有内容
        if not edit.toPlainText().strip() and "data:image" not in text:
            self._set_status("⚠ 模板内容为空 (无文本且无图片), 未保存。", "#E6A23C")
            return
        if self._save_template():
            self._set_status("✅ 模板已保存。", "#67C23A")
        else:
            self._set_status("⚠ 模板未保存 (未选择文档类型/芯片)。", "#E6A23C")

    def _save_template(self, doc_type=None, chip=None) -> bool:
        """把模板编辑区当前内容写入内存配置与 config.json (含图片, HTML 形式)。
        doc_type 缺省时为当前选中类型; 切换类型前应显式传旧类型, 避免误写新类型。
        chip 仅烧录指导使用: 切换芯片时 combo 已指向新芯片, 必须显式传旧芯片名落盘。
        返回 True 表示已落盘。"""
        doc_type = doc_type or self._selected_type()
        if not doc_type:
            return False
        text = _edit_save_text(self.template_preview_edit)
        text = (text or "").strip()
        # 空内容 (无文本且无图片) 不落盘, 保护默认模板与既有内容
        if not self.template_preview_edit.toPlainText().strip() and "data:image" not in text:
            return False
        cfg_types = self.cfg.config.setdefault("text_polish", {}).setdefault("types", {})
        if doc_type == "烧录指导":
            chip = chip or self._selected_chip()
            if not chip:
                return False
            burn = self.polish_types.setdefault("烧录指导", {})
            chip_cfg = burn.setdefault("chips", {}).setdefault(chip, {})
            if not isinstance(chip_cfg, dict):
                chip_cfg = {}
            chip_cfg["template"] = text
            burn["chips"][chip] = chip_cfg
            # 写回 config.json: 归一化残留旧结构后再更新
            burn_cfg = cfg_types.setdefault("烧录指导", {})
            normalized = self._normalize_burn_cfg(burn_cfg)
            n_chip = normalized.setdefault("chips", {}).setdefault(chip, {})
            n_chip["template"] = text
            cfg_types["烧录指导"] = normalized
        else:
            data = copy.deepcopy(self.polish_types.get(doc_type, {}))
            data["template"] = text
            self.polish_types[doc_type] = data
            cfg_types[doc_type] = data
        self.cfg.save_config()
        self._loaded_template_text = text
        return True

    def polish(self):
        """调用 DeepSeek 按所选类型润色文本"""
        if self.ai_thread is not None:
            return  # 上次润色仍在进行 (对象有效且未结束), 忽略连点
        type_cfg = self._resolve_type_cfg()
        if type_cfg is None:
            self._set_status(
                "⚠ 当前文档类型未配置, 请先在模板编辑区填写内容并点『💾 保存模板』, "
                "还可通过「📌 限制要求」设置角色与限制条件。",
                "#E6A23C",
            )
            return
        raw = _plain_with_img_mark(self.template_preview_edit.toHtml()).strip()
        if not raw:
            self._set_status(
                "⚠ 请先在模板中输入内容, 模板即润色内容。",
                "#E6A23C",
            )
            return
        # 超长输入截断, 避免超出 API token 限制导致请求失败
        MAX_INPUT_CHARS = 8000
        if len(raw) > MAX_INPUT_CHARS:
            raw = raw[:MAX_INPUT_CHARS]
            self._set_status(
                f"⚠ 输入过长, 已截断至前 {MAX_INPUT_CHARS} 字后发送。", "#E6A23C",
            )

        api = load_api_config(self.cfg)
        if not api["api_key"]:
            self._set_status(
                "⚠ 未配置 DeepSeek API Key (config.json → power_conversion.api.api_key)。",
                "#E6A23C",
            )
            return

        doc_title = self._doc_title()
        self.polish_btn.setEnabled(False)
        self._set_status(f"⏳ 正在按「{doc_title}」润色, 请稍候 (约 10~30 秒)…", "#409EFF")

        # 结果窗口展示的模板 = 用户编辑后的实际内容 (含图片则保留 HTML)
        type_cfg = copy.deepcopy(type_cfg)
        type_cfg["template"] = self.template_preview_edit.toHtml()

        # 打开润色结果独立窗口 (前台展示本次使用的模板 + 加载状态)
        self._open_result_dialog(doc_title, type_cfg)

        prompt = f"请将以下原始文本润色为规范的《{doc_title}》文档:\n\n{raw}"
        self.ai_thread = DeepSeekThread(
            api["api_key"],
            prompt,
            base_url=api["base_url"],
            model=api["model"],
            temperature=api["temperature"],
            max_tokens=api["max_tokens"],
            system_prompt=self._build_system_prompt(type_cfg, include_template=False),
        )
        self.ai_thread.succeeded.connect(self._on_succeeded)
        self.ai_thread.failed.connect(self._on_failed)
        self.ai_thread.finished.connect(self._on_ai_thread_finished)
        self.ai_thread.start()

    def _td_backup_templates(self):
        """一键把全部模板配置备份到腾讯文档 (防止配置丢失)"""
        if self.td_thread is not None:
            return  # 上次备份仍在进行
        td = self.cfg.config.get("tencent_docs", {}) or {}
        access_token = str(td.get("access_token", "") or "")
        client_id = str(td.get("client_id", "") or "")
        client_secret = str(td.get("client_secret", "") or "")
        open_id = str(td.get("open_id", "") or "")
        if not access_token and (not client_id or not client_secret):
            self._set_status(
                "⚠ 未配置腾讯文档凭证, 请到 系统设置 → 腾讯文档同步 中填写 Access Token 或 Client ID/Secret。",
                "#E6A23C",
            )
            return
        from datetime import datetime

        html = build_config_backup_html(self.cfg.config, "文本润色配置备份")
        self.td_backup_btn.setEnabled(False)
        self._set_status("⏳ 正在备份模板到腾讯文档 (约 10~30 秒)…", "#409EFF")
        self.td_thread = TencentDocsThread(
            TencentDocsClient(
                client_id, client_secret, access_token=access_token, open_id=open_id
            ),
            "backup",
            payload=html,
            doc_name=f"文本润色配置备份 {datetime.now().strftime('%Y-%m-%d %H%M')}",
        )
        self.td_thread.succeeded.connect(self._on_td_backup_succeeded)
        self.td_thread.failed.connect(self._on_td_backup_failed)
        self.td_thread.finished.connect(self._on_td_backup_finished)
        self.td_thread.start()

    def _on_td_backup_finished(self):
        """备份线程结束: 清空引用并恢复按钮"""
        self.td_thread = None
        self.td_backup_btn.setEnabled(True)

    def _on_td_backup_succeeded(self, url):
        """备份成功: 展示在线文档链接"""
        if url.startswith("http"):
            self._set_status(
                f"✅ 备份成功! 在线文档: {url} (旧版本自动保留)", "#67C23A"
            )
            td = self.cfg.config.setdefault("tencent_docs", {})
            td["last_url"] = url
            self.cfg.save_config()
        else:
            self._set_status(f"✅ {url}", "#67C23A")

    def _on_td_backup_failed(self, error):
        """备份失败"""
        self._set_status(f"❌ 备份失败: {error}", "#F56C6C")

    def closeEvent(self, event):
        """窗口关闭: 模板有未保存修改先确认 (取消则不关), 再关闭结果窗口, 等待线程结束"""
        if not self.flush_pending_save():
            event.ignore()
            return
        if self._result_dlg is not None:
            self._result_dlg.close()
            self._result_dlg = None
        for name in ("ai_thread", "td_thread"):
            thread = getattr(self, name)
            if thread is not None and thread.isRunning():
                thread.requestInterruption()  # 无副作用; 线程有 60s 网络超时兜底
                thread.wait(5000)
            if thread is not None and not thread.isRunning():
                setattr(self, name, None)
        super().closeEvent(event)

    def _on_ai_thread_finished(self):
        """线程结束 (成功或失败): 清空引用由 Python GC 回收, 并恢复按钮。
        不再用 deleteLater, 否则 Python 引用指向已删除对象, 再次润色即闪退。"""
        self.ai_thread = None
        self.polish_btn.setEnabled(True)

    def _open_result_dialog(self, doc_title: str, type_cfg: dict) -> "PolishResultDialog":
        """打开 (或复用) 润色结果独立窗口, 前台展示本次使用的模板"""
        if self._result_dlg is not None:
            self._result_dlg.close()
        self._result_dlg = PolishResultDialog(doc_title, type_cfg, self)
        self._result_dlg.set_loading()
        self._result_dlg.show()
        self._result_dlg.raise_()
        self._result_dlg.activateWindow()
        return self._result_dlg

    def _current_result_dialog(self) -> "PolishResultDialog | None":
        """获取当前可见的结果窗口; 用户已关闭则返回 None (由调用方重建)"""
        dlg = self._result_dlg
        if dlg is None or dlg.isHidden():
            return None
        return dlg

    def _on_succeeded(self, text):
        """润色成功: 写入结果窗口并 Markdown 渲染 (窗口已关则重建)"""
        dlg = self._current_result_dialog()
        if dlg is None:
            dlg = self._open_result_dialog(self._doc_title(), self._resolve_type_cfg() or {})
        dlg.set_result(text)
        self._set_status("✅ 润色完成, 结果已在新窗口展示。", "#67C23A")
        self.polish_btn.setEnabled(True)

    def _on_failed(self, error):
        """润色失败: 错误信息写入结果窗口"""
        dlg = self._current_result_dialog()
        if dlg is None:
            dlg = self._open_result_dialog(self._doc_title(), self._resolve_type_cfg() or {})
        dlg.set_error(error)
        self._set_status("❌ 请求失败, 请检查 API Key 与网络。", "#F56C6C")
        self.polish_btn.setEnabled(True)

    # ==================== 工具方法 ====================
    def _clear_input(self):
        self.template_preview_edit.clear()
        self._set_status("")

    def _set_status(self, text, color="#909399"):
        self.status_label.setText(text)
        self.status_label.setStyleSheet(
            f"color: {color}; background: transparent; border: none;"
        )

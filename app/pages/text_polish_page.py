"""
文本润色页面

功能:
- 将用户输入的原始文本按类型润色为规范、专业的工程文档
- 支持类型: 工艺要求 / 测试流程 / 烧录指导
- 基于 DeepSeek API 后台润色, 不阻塞界面

使用说明:
- 选择类型 → 粘贴原始文本 → 点击"🤖 AI 润色"
- 结果以 Markdown 渲染在下方结果区, 可手动复制
"""

from pathlib import Path

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QFont
from PyQt6.QtWidgets import (
    QButtonGroup, QComboBox, QDialog, QFrame, QHBoxLayout, QLabel, QLineEdit,
    QPlainTextEdit, QPushButton, QRadioButton, QTextBrowser, QTextEdit,
    QVBoxLayout, QWidget,
)

from app.core.config_manager import ConfigManager
from app.core.deepseek_client import DeepSeekThread, load_api_config

# 各文档类型默认模板与限制 (config.json → text_polish.types 缺失时回退到此处)
DEFAULT_TEXT_POLISH_TYPES = {
    "工艺要求": {
        "system_role": "你是一名资深电子制造工艺工程师。",
        "template": (
            "请将用户提供的原始文本润色为规范的《工艺要求》文档, 按以下模板组织内容:\n"
            "一、适用范围\n"
            "二、作业准备\n"
            "三、工艺参数\n"
            "四、操作步骤\n"
            "五、检验要求\n"
            "六、注意事项"
        ),
        "constraints": [
            "条理清晰, 分条列出",
            "术语规范, 语言专业严谨, 使用规范的中文工程用语",
            "保留原文所有关键数据与约束, 不凭空增加内容",
            "如原文缺少必要信息, 用【待补充】标注",
            "使用 Markdown 格式输出",
        ],
    },
    "测试流程": {
        "system_role": "你是一名资深电子产品测试工程师。",
        "template": (
            "请将用户提供的原始文本润色为规范的《测试流程》文档, 按以下模板组织内容:\n"
            "一、测试目的\n"
            "二、测试条件 (环境、设备、治具)\n"
            "三、测试步骤 (按 1. 2. 3. 编号)\n"
            "四、判定标准\n"
            "五、异常处理\n"
            "六、记录要求"
        ),
        "constraints": [
            "按步骤编号列出 (1. 2. 3.), 明确前置条件、操作步骤、判定标准",
            "术语规范, 语言专业严谨",
            "保留原文所有测试项、参数与判定阈值",
            "如原文缺少必要信息, 用【待补充】标注",
            "使用 Markdown 格式输出",
        ],
    },
    "烧录指导": {
        "system_role": "你是一名资深嵌入式烧录工艺工程师。",
        "template": (
            "请将用户提供的原始文本润色为规范的《烧录指导》文档, 按以下模板组织内容:\n"
            "一、烧录工具与软件\n"
            "二、连接方式\n"
            "三、操作步骤\n"
            "四、校验方式\n"
            "五、注意事项"
        ),
        "constraints": [
            "条理清晰, 分条列出: 烧录工具、连接方式、操作步骤、校验与注意事项",
            "术语规范, 语言专业严谨",
            "保留原文所有关键参数 (型号、地址、命令、校验方式等)",
            "如原文缺少必要信息, 用【待补充】标注",
            "使用 Markdown 格式输出",
        ],
    },
}

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


class TextPolishConfigDialog(QDialog):
    """文本润色模板与限制配置窗口 (保存到 config.json → text_polish.types)"""

    def __init__(self, cfg, polish_types, parent=None):
        super().__init__(parent)
        self.cfg = cfg
        self.polish_types = polish_types
        self.setWindowTitle("⚙️ 文本润色模板配置")
        self.resize(720, 640)
        self.setMinimumSize(560, 500)

        root = QVBoxLayout(self)
        root.setContentsMargins(20, 16, 20, 16)
        root.setSpacing(12)

        # 标题与说明
        title = QLabel("⚙️ 文本润色模板与限制配置")
        title.setFont(QFont("Microsoft YaHei", 14, QFont.Weight.Bold))
        root.addWidget(title)
        hint = QLabel(
            "选择文档类型, 编辑其角色设定、文档模板与限制条件。"
            "保存后写入 config.json → text_polish.types, 下次润色立即生效。"
        )
        hint.setFont(QFont("Microsoft YaHei", 10))
        hint.setStyleSheet("color: #909399; background: transparent; border: none;")
        hint.setWordWrap(True)
        root.addWidget(hint)

        # 类型选择
        type_row = QHBoxLayout()
        type_label = QLabel("文档类型:")
        type_label.setFont(QFont("Microsoft YaHei", 11))
        type_row.addWidget(type_label)
        self.type_combo = QComboBox()
        self.type_combo.addItems(list(polish_types.keys()))
        self.type_combo.setFont(QFont("Microsoft YaHei", 11))
        self.type_combo.setMinimumWidth(200)
        self.type_combo.currentTextChanged.connect(self._load_type)
        type_row.addWidget(self.type_combo)
        type_row.addStretch()
        root.addLayout(type_row)

        # 角色设定
        role_label = QLabel("角色设定 (system_role)")
        role_label.setStyleSheet(SECTION_TITLE_STYLE)
        root.addWidget(role_label)
        self.role_edit = QLineEdit()
        self.role_edit.setFont(QFont("Microsoft YaHei", 11))
        self.role_edit.setPlaceholderText("例如: 你是一名资深电子制造工艺工程师。")
        self.role_edit.setStyleSheet(
            "QLineEdit { border: 1px solid #DCDFE6; border-radius: 6px;"
            "padding: 6px 10px; background: white; }"
            "QLineEdit:focus { border-color: #409EFF; }"
        )
        root.addWidget(self.role_edit)

        # 文档模板
        template_label = QLabel("文档模板 (template)")
        template_label.setStyleSheet(SECTION_TITLE_STYLE)
        root.addWidget(template_label)
        self.template_edit = QPlainTextEdit()
        self.template_edit.setFont(QFont("Microsoft YaHei", 11))
        self.template_edit.setPlaceholderText(
            "每行一个章节, AI 将按此模板组织文档内容…\n例如:\n一、适用范围\n二、作业准备\n三、工艺参数"
        )
        self.template_edit.setMinimumHeight(140)
        self.template_edit.setStyleSheet(
            "QPlainTextEdit { border: 1px solid #DCDFE6; border-radius: 6px;"
            "padding: 6px; background: white; }"
            "QPlainTextEdit:focus { border-color: #409EFF; }"
        )
        root.addWidget(self.template_edit, 1)

        # 限制条件
        constraints_label = QLabel("限制条件 (constraints, 每行一条)")
        constraints_label.setStyleSheet(SECTION_TITLE_STYLE)
        root.addWidget(constraints_label)
        self.constraints_edit = QPlainTextEdit()
        self.constraints_edit.setFont(QFont("Microsoft YaHei", 11))
        self.constraints_edit.setPlaceholderText(
            "每行一条限制, 例如:\n条理清晰, 分条列出\n保留原文所有关键数据与约束, 不凭空增加内容"
        )
        self.constraints_edit.setMinimumHeight(120)
        self.constraints_edit.setStyleSheet(
            "QPlainTextEdit { border: 1px solid #DCDFE6; border-radius: 6px;"
            "padding: 6px; background: white; }"
            "QPlainTextEdit:focus { border-color: #409EFF; }"
        )
        root.addWidget(self.constraints_edit, 1)

        # 底部按钮
        btn_row = QHBoxLayout()
        btn_row.addStretch()
        restore_btn = QPushButton("恢复该类型默认")
        restore_btn.setMinimumHeight(36)
        restore_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        restore_btn.setStyleSheet(SECONDARY_BTN_STYLE)
        restore_btn.clicked.connect(self._restore_default)
        btn_row.addWidget(restore_btn)

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

        # 加载第一个类型
        self._load_type(self.type_combo.currentText())

    # ==================== 配置窗口逻辑 ====================
    def _load_type(self, name):
        """将指定类型的配置加载到编辑框"""
        cfg = self.polish_types.get(name, {})
        self.role_edit.setText(cfg.get("system_role", ""))
        self.template_edit.setPlainText(cfg.get("template", ""))
        constraints = cfg.get("constraints", [])
        if isinstance(constraints, str):
            constraints = [constraints]
        self.constraints_edit.setPlainText("\n".join(str(c) for c in constraints))

    def _parse_constraints(self) -> list:
        """把限制文本按行拆分为列表 (忽略空行)"""
        return [line.strip() for line in self.constraints_edit.toPlainText().splitlines() if line.strip()]

    def _restore_default(self):
        """将当前类型恢复为内置默认模板与限制"""
        name = self.type_combo.currentText()
        defaults = DEFAULT_TEXT_POLISH_TYPES.get(name)
        if not defaults:
            return
        self.role_edit.setText(defaults["system_role"])
        self.template_edit.setPlainText(defaults["template"])
        self.constraints_edit.setPlainText("\n".join(defaults["constraints"]))

    def _save(self):
        """保存到内存配置并写回 config.json"""
        name = self.type_combo.currentText()
        if not name:
            return
        data = {
            "system_role": self.role_edit.text().strip(),
            "template": self.template_edit.toPlainText().strip(),
            "constraints": self._parse_constraints(),
        }
        # 更新传入的配置引用 (页面可感知)
        self.polish_types[name] = data
        # 写回 config.json (不存在时自动创建段)
        cfg_types = self.cfg.config.setdefault("text_polish", {}).setdefault("types", {})
        cfg_types[name] = data
        self.cfg.save_config()
        self.accept()


class TextPolishPage(QWidget):
    """文本润色页面"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.cfg = ConfigManager(str(Path(__file__).resolve().parents[2] / "config.json"))
        self.polish_types = self._load_polish_types()
        self.ai_thread = None
        self._setup_ui()

    # ==================== UI 构建 ====================
    def _setup_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(24, 20, 24, 20)
        root.setSpacing(16)

        # 标题区
        title = QLabel("✍️ 文本润色")
        title.setFont(QFont("Microsoft YaHei", 20, QFont.Weight.Bold))
        root.addWidget(title)
        subtitle = QLabel("将原始文本润色为规范的工程文档 · 支持工艺要求 / 测试流程 / 烧录指导 · 模板与限制可在右侧配置")
        subtitle.setFont(QFont("Microsoft YaHei", 10))
        subtitle.setStyleSheet("color: #909399; background: transparent; border: none;")
        root.addWidget(subtitle)

        # 1. 类型选择卡片
        type_card = QFrame()
        type_card.setStyleSheet(CARD_STYLE)
        type_layout = QVBoxLayout(type_card)
        type_layout.setContentsMargins(16, 12, 16, 12)
        type_layout.setSpacing(10)

        type_title = QLabel("文档类型")
        type_title.setStyleSheet(SECTION_TITLE_STYLE)
        type_layout.addWidget(type_title)

        type_row = QHBoxLayout()
        type_row.setSpacing(24)
        self.type_group = QButtonGroup(self)
        for text in self._type_names():
            rb = QRadioButton(text)
            rb.setFont(QFont("Microsoft YaHei", 11))
            rb.setCursor(Qt.CursorShape.PointingHandCursor)
            rb.setStyleSheet(
                "QRadioButton { color: #303133; }"
                "QRadioButton::indicator { width: 16px; height: 16px; }"
            )
            self.type_group.addButton(rb)
            type_row.addWidget(rb)
        type_row.addStretch()
        type_layout.addLayout(type_row)
        root.addWidget(type_card)

        # 2. 原文输入卡片
        input_card = QFrame()
        input_card.setStyleSheet(CARD_STYLE)
        input_layout = QVBoxLayout(input_card)
        input_layout.setContentsMargins(16, 12, 16, 12)
        input_layout.setSpacing(10)

        input_title = QLabel("原始文本")
        input_title.setStyleSheet(SECTION_TITLE_STYLE)
        input_layout.addWidget(input_title)

        self.input_edit = QTextEdit()
        self.input_edit.setPlaceholderText(
            "在此粘贴需要润色的原始文本…\n例如: 焊接时温度不能太高, 大概 260 度左右, 时间也别太长, 三五秒就行…"
        )
        self.input_edit.setFont(QFont("Microsoft YaHei", 11))
        self.input_edit.setMinimumHeight(140)
        self.input_edit.setStyleSheet(
            "QTextEdit { border: 1px solid #DCDFE6; border-radius: 8px;"
            "padding: 8px; background: #FAFAFA; }"
            "QTextEdit:focus { border-color: #409EFF; background: white; }"
        )
        input_layout.addWidget(self.input_edit)
        root.addWidget(input_card, 1)

        # 3. 操作按钮行
        btn_row = QHBoxLayout()
        btn_row.setSpacing(12)

        self.polish_btn = QPushButton("🤖 AI 润色")
        self.polish_btn.setMinimumHeight(40)
        self.polish_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.polish_btn.setStyleSheet(
            "QPushButton { background: #409EFF; color: white; border: none;"
            "border-radius: 8px; padding: 6px 20px; font-weight: bold; font-size: 13px; }"
            "QPushButton:hover { background: #66B1FF; }"
            "QPushButton:pressed { background: #337ECC; }"
            "QPushButton:disabled { background: #A0CFFF; }"
        )
        self.polish_btn.clicked.connect(self.polish)

        self.clear_btn = QPushButton("清空输入")
        self.clear_btn.setMinimumHeight(40)
        self.clear_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.clear_btn.setStyleSheet(SECONDARY_BTN_STYLE)
        self.clear_btn.clicked.connect(self._clear_input)

        self.config_btn = QPushButton("⚙️ 模板配置")
        self.config_btn.setMinimumHeight(40)
        self.config_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.config_btn.setStyleSheet(SECONDARY_BTN_STYLE)
        self.config_btn.clicked.connect(self.open_config_dialog)

        self.status_label = QLabel("")
        self.status_label.setStyleSheet("color: #909399; background: transparent; border: none;")

        btn_row.addWidget(self.polish_btn)
        btn_row.addWidget(self.clear_btn)
        btn_row.addWidget(self.config_btn)
        btn_row.addWidget(self.status_label)
        btn_row.addStretch()
        root.addLayout(btn_row)

        # 4. 润色结果卡片
        result_card = QFrame()
        result_card.setStyleSheet(CARD_STYLE)
        result_layout = QVBoxLayout(result_card)
        result_layout.setContentsMargins(16, 12, 16, 12)
        result_layout.setSpacing(10)

        result_title = QLabel("润色结果")
        result_title.setStyleSheet(SECTION_TITLE_STYLE)
        result_layout.addWidget(result_title)

        self.result_browser = QTextBrowser()
        self.result_browser.setOpenExternalLinks(True)
        self.result_browser.setFont(QFont("Microsoft YaHei", 11))
        self.result_browser.setMinimumHeight(160)
        self.result_browser.setStyleSheet(
            "QTextBrowser { border: 1px solid #DCDFE6; border-radius: 8px;"
            "padding: 10px; background: white; }"
            "QTextBrowser a { color: #409EFF; }"
        )
        result_layout.addWidget(self.result_browser, 1)
        root.addWidget(result_card, 1)

    # ==================== 润色逻辑 ====================
    # ==================== 模板与限制配置 ====================
    def _load_polish_types(self) -> dict:
        """从 config.json → text_polish.types 加载各类型模板与限制, 缺失项回退默认"""
        cfg_types = self.cfg.config.get("text_polish", {}).get("types", {})
        if not isinstance(cfg_types, dict):
            cfg_types = {}
        types = {}
        for name, defaults in DEFAULT_TEXT_POLISH_TYPES.items():
            item = cfg_types.get(name, {})
            if not isinstance(item, dict):
                item = {}
            types[name] = {
                "system_role": str(item.get("system_role", defaults["system_role"])),
                "template": str(item.get("template", defaults["template"])),
                "constraints": item.get("constraints", defaults["constraints"]),
            }
        # 配置中新增的类型也纳入 (便于后续扩展, 无需改代码)
        for name, item in cfg_types.items():
            if name in types or not isinstance(item, dict):
                continue
            types[name] = {
                "system_role": str(item.get("system_role", "")),
                "template": str(item.get("template", "")),
                "constraints": item.get("constraints", []),
            }
        return types

    def _type_names(self) -> list:
        """类型顺序: 默认三种在前, 配置新增的排后"""
        defaults = list(DEFAULT_TEXT_POLISH_TYPES)
        return defaults + [n for n in self.polish_types if n not in defaults]

    def _build_system_prompt(self, type_cfg: dict) -> str:
        """由 system_role + template + constraints 组装 system 提示词"""
        parts = [type_cfg["system_role"]] if type_cfg.get("system_role") else []
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

    def _selected_type(self) -> str:
        btn = self.type_group.checkedButton()
        return btn.text() if btn else "工艺要求"

    def open_config_dialog(self):
        """打开模板与限制配置窗口"""
        dlg = TextPolishConfigDialog(self.cfg, self.polish_types, self)
        if dlg.exec():
            # 配置可能被修改, 重新加载以同步界面
            self.polish_types = self._load_polish_types()
            self._set_status("✅ 配置已保存, 新模板与限制将在下次润色时生效。", "#67C23A")

    def polish(self):
        """调用 DeepSeek 按所选类型润色文本"""
        doc_type = self._selected_type()
        type_cfg = self.polish_types.get(doc_type)
        if type_cfg is None:
            self._set_status(
                "⚠ 该文档类型未配置模板与限制, 请在 config.json → text_polish.types 中配置。",
                "#E6A23C",
            )
            return
        raw = self.input_edit.toPlainText().strip()
        if not raw:
            self._set_status("⚠ 请先输入需要润色的原始文本。", "#E6A23C")
            return

        api = load_api_config(self.cfg)
        if not api["api_key"]:
            self._set_status(
                "⚠ 未配置 DeepSeek API Key (config.json → power_conversion.api.api_key)。",
                "#E6A23C",
            )
            return

        self.polish_btn.setEnabled(False)
        self._set_status(f"⏳ 正在按「{doc_type}」润色, 请稍候 (约 10~30 秒)…", "#409EFF")
        self.result_browser.setPlainText("")

        prompt = f"请将以下原始文本润色为规范的《{doc_type}》文档:\n\n{raw}"
        self.ai_thread = DeepSeekThread(
            api["api_key"],
            prompt,
            base_url=api["base_url"],
            model=api["model"],
            temperature=api["temperature"],
            max_tokens=api["max_tokens"],
            system_prompt=self._build_system_prompt(type_cfg),
        )
        self.ai_thread.succeeded.connect(self._on_succeeded)
        self.ai_thread.failed.connect(self._on_failed)
        self.ai_thread.finished.connect(self.ai_thread.deleteLater)
        self.ai_thread.start()

    def _on_succeeded(self, text):
        """润色成功: Markdown 渲染结果"""
        self.result_browser.setMarkdown(text)
        self._set_status("✅ 润色完成, 可复制使用。", "#67C23A")
        self.polish_btn.setEnabled(True)

    def _on_failed(self, error):
        """润色失败"""
        self._set_status("❌ 请求失败, 请检查 API Key 与网络。", "#F56C6C")
        self.result_browser.setPlainText(f"❌ DeepSeek 请求失败:\n{error}")
        self.polish_btn.setEnabled(True)

    # ==================== 工具方法 ====================
    def _clear_input(self):
        self.input_edit.clear()
        self.result_browser.clear()
        self._set_status("")

    def _set_status(self, text, color="#909399"):
        self.status_label.setText(text)
        self.status_label.setStyleSheet(
            f"color: {color}; background: transparent; border: none;"
        )

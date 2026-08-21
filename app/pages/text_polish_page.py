"""
文本润色页面

功能:
- 将用户输入的原始文本按类型润色为规范、专业的工程文档
- 支持类型: 工艺要求 / 测试流程 / 烧录指导
- 烧录指导: 按芯片厂商 (中微爱芯/十速/兆易创新/赛元…) × 烧录方式 (在线/离线) 使用独立模板
  - 在线烧录: 芯片已贴装, 在 PCBA 上手工烧录, 需指明 PCBA 烧录口
  - 离线烧录: 芯片未贴装, 在烧录机上批量烧录, 需指明芯片烧录引脚
- 模板与限制均可通过「⚙️ 模板配置」窗口修改, 并支持新增芯片
- 基于 DeepSeek API 后台润色, 不阻塞界面

使用说明:
- 选择类型 (烧录指导需再选芯片与烧录方式) → 粘贴原始文本 → 点击"🤖 AI 润色"
- 结果以 Markdown 渲染在下方结果区, 可手动复制
"""

import copy
from pathlib import Path

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QFont
from PyQt6.QtWidgets import (
    QButtonGroup, QComboBox, QDialog, QFrame, QHBoxLayout, QLabel, QLineEdit,
    QPlainTextEdit, QPushButton, QRadioButton, QTextBrowser, QTextEdit,
    QVBoxLayout, QWidget,
)

from app.core.config_manager import ConfigManager, app_root
from app.core.deepseek_client import DeepSeekThread, load_api_config

# 默认文档类型顺序 (模板/限制内容来自 config_manager 出厂默认配置, 页面不再重复维护)
DEFAULT_TYPE_NAMES = ("工艺要求", "测试流程", "烧录指导")
DEFAULT_BURN_MODES = ("在线烧录", "离线烧录")

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


class TextPolishConfigDialog(QDialog):
    """文本润色模板与限制配置窗口 (保存到 config.json → text_polish.types)

    支持:
    - 工艺要求 / 测试流程: 直接编辑角色/模板/限制
    - 烧录指导: 按 芯片 × 烧录方式 编辑独立模板, 并可新增芯片
    """

    def __init__(self, cfg, polish_types, parent=None):
        super().__init__(parent)
        self.cfg = cfg
        self.polish_types = polish_types
        self.setWindowTitle("⚙️ 文本润色模板配置")
        self.resize(760, 680)
        self.setMinimumSize(580, 520)

        root = QVBoxLayout(self)
        root.setContentsMargins(20, 16, 20, 16)
        root.setSpacing(12)

        # 标题与说明
        title = QLabel("⚙️ 文本润色模板与限制配置")
        title.setFont(QFont("Microsoft YaHei", 14, QFont.Weight.Bold))
        root.addWidget(title)
        hint = QLabel(
            "选择文档类型编辑模板。烧录指导按「芯片 × 烧录方式」配置独立模板, 可新增芯片。"
            "保存后写入 config.json → text_polish.types, 下次润色立即生效。"
        )
        hint.setFont(QFont("Microsoft YaHei", 10))
        hint.setStyleSheet("color: #909399; background: transparent; border: none;")
        hint.setWordWrap(True)
        root.addWidget(hint)

        # 文档类型选择
        type_row = QHBoxLayout()
        type_label = QLabel("文档类型:")
        type_label.setFont(QFont("Microsoft YaHei", 11))
        type_row.addWidget(type_label)
        self.type_combo = QComboBox()
        self.type_combo.addItems(list(polish_types.keys()) or list(DEFAULT_TYPE_NAMES))
        self.type_combo.setFont(QFont("Microsoft YaHei", 11))
        self.type_combo.setMinimumWidth(180)
        self.type_combo.currentTextChanged.connect(self._load_current)
        type_row.addWidget(self.type_combo)
        type_row.addStretch()
        root.addLayout(type_row)

        # 芯片 / 烧录方式选择 (仅烧录指导)
        self.burn_row = QFrame()
        burn_layout = QHBoxLayout(self.burn_row)
        burn_layout.setContentsMargins(0, 0, 0, 0)
        burn_layout.setSpacing(8)
        chip_label = QLabel("芯片:")
        chip_label.setFont(QFont("Microsoft YaHei", 11))
        burn_layout.addWidget(chip_label)
        self.chip_combo = QComboBox()
        self.chip_combo.setFont(QFont("Microsoft YaHei", 11))
        self.chip_combo.setMinimumWidth(150)
        self.chip_combo.setStyleSheet(COMBO_STYLE)
        self.chip_combo.currentTextChanged.connect(self._load_current)
        burn_layout.addWidget(self.chip_combo)
        mode_label = QLabel("烧录方式:")
        mode_label.setFont(QFont("Microsoft YaHei", 11))
        burn_layout.addWidget(mode_label)
        self.mode_combo = QComboBox()
        self.mode_combo.setFont(QFont("Microsoft YaHei", 11))
        self.mode_combo.setMinimumWidth(120)
        self.mode_combo.setStyleSheet(COMBO_STYLE)
        self.mode_combo.currentTextChanged.connect(self._load_current)
        burn_layout.addWidget(self.mode_combo)
        self.new_chip_edit = QLineEdit()
        self.new_chip_edit.setFont(QFont("Microsoft YaHei", 11))
        self.new_chip_edit.setPlaceholderText("新芯片名…")
        self.new_chip_edit.setStyleSheet(INPUT_STYLE)
        self.new_chip_edit.setMaximumWidth(140)
        burn_layout.addWidget(self.new_chip_edit)
        add_chip_btn = QPushButton("＋ 新增芯片")
        add_chip_btn.setMinimumHeight(32)
        add_chip_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        add_chip_btn.setStyleSheet(SECONDARY_BTN_STYLE)
        add_chip_btn.clicked.connect(self._add_chip)
        burn_layout.addWidget(add_chip_btn)
        burn_layout.addStretch()
        root.addWidget(self.burn_row)

        # 角色设定
        role_label = QLabel("角色设定 (system_role)")
        role_label.setStyleSheet(SECTION_TITLE_STYLE)
        root.addWidget(role_label)
        self.role_edit = QLineEdit()
        self.role_edit.setFont(QFont("Microsoft YaHei", 11))
        self.role_edit.setPlaceholderText("例如: 你是一名资深电子制造工艺工程师。")
        self.role_edit.setStyleSheet(INPUT_STYLE)
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
        self.template_edit.setMinimumHeight(130)
        self.template_edit.setStyleSheet(EDIT_STYLE)
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
        self.constraints_edit.setMinimumHeight(110)
        self.constraints_edit.setStyleSheet(EDIT_STYLE)
        root.addWidget(self.constraints_edit, 1)

        # 底部按钮
        btn_row = QHBoxLayout()
        btn_row.addStretch()
        restore_btn = QPushButton("恢复默认")
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
        self._load_current(self.type_combo.currentText())

    # ==================== 配置窗口逻辑 ====================
    def _current_simple(self) -> bool:
        return self.type_combo.currentText() != "烧录指导"

    def _burn_cfg(self) -> dict:
        return self.polish_types.get("烧录指导", {})

    def _load_current(self, *_):
        """根据当前选择 (类型/芯片/烧录方式) 加载配置到编辑框"""
        name = self.type_combo.currentText()
        is_burn = not self._current_simple()
        self.burn_row.setVisible(is_burn)
        if is_burn:
            self._refresh_chip_combo()
            self._refresh_mode_combo()
            cfg = self._current_burn_mode_cfg()
        else:
            cfg = self.polish_types.get(name, {})
        self.role_edit.setText(cfg.get("system_role", ""))
        self.template_edit.setPlainText(cfg.get("template", ""))
        constraints = cfg.get("constraints", [])
        if isinstance(constraints, str):
            constraints = [constraints]
        self.constraints_edit.setPlainText("\n".join(str(c) for c in constraints))

    def _refresh_chip_combo(self):
        chips = self._burn_cfg().get("chips", {})
        current = self.chip_combo.currentText()
        self.chip_combo.blockSignals(True)
        self.chip_combo.clear()
        self.chip_combo.addItems(list(chips.keys()))
        if current in chips:
            self.chip_combo.setCurrentText(current)
        self.chip_combo.blockSignals(False)

    def _refresh_mode_combo(self):
        burn = self._burn_cfg()
        chip = self.chip_combo.currentText()
        modes = burn.get("modes") or list(DEFAULT_BURN_MODES)
        chip_cfg = burn.get("chips", {}).get(chip, {})
        available = [m for m in modes if isinstance(chip_cfg.get(m), dict)] or list(modes)
        current = self.mode_combo.currentText()
        self.mode_combo.blockSignals(True)
        self.mode_combo.clear()
        self.mode_combo.addItems(available)
        if current in available:
            self.mode_combo.setCurrentText(current)
        self.mode_combo.blockSignals(False)

    def _current_burn_mode_cfg(self) -> dict:
        chip = self.chip_combo.currentText()
        mode = self.mode_combo.currentText()
        if not chip or not mode:
            return {}
        return self._burn_cfg().get("chips", {}).get(chip, {}).get(mode, {})

    def _add_chip(self):
        """新增芯片: 初始化在线/离线两套通用模板"""
        name = self.new_chip_edit.text().strip()
        if not name:
            return
        burn = self.polish_types.setdefault("烧录指导", {})
        burn.setdefault("modes", list(DEFAULT_BURN_MODES))
        chips = burn.setdefault("chips", {})
        if name not in chips:
            chips[name] = self._generic_chip_defaults(name)
        self.new_chip_edit.clear()
        self._refresh_chip_combo()
        self.chip_combo.setCurrentText(name)
        self._refresh_mode_combo()
        self._load_current()

    def _generic_chip_defaults(self, chip: str) -> dict:
        """为新芯片生成在线/离线两套通用模板 (可在窗口中进一步微调)"""
        out = {}
        for mode in DEFAULT_BURN_MODES:
            if mode == "在线烧录":
                role = (
                    f"你是一名资深嵌入式烧录工艺工程师, 精通 {chip} 芯片的在线烧录。"
                    "在线烧录指芯片已贴装在 PCBA 上, 通过 PCBA 上的烧录口手工烧录。"
                )
                template = (
                    f"请将用户提供的原始文本润色为规范的《{chip} 在线烧录指导》文档, 按以下模板组织内容:\n"
                    "一、烧录工具与软件\n"
                    "二、PCBA 烧录口说明 (接口位置、引脚定义、顺序)\n"
                    "三、连接方式\n"
                    "四、烧录步骤\n"
                    "五、校验与注意事项"
                )
            else:
                role = (
                    f"你是一名资深嵌入式烧录工艺工程师, 精通 {chip} 芯片的离线烧录。"
                    "离线烧录指芯片未贴装时, 在烧录机上对芯片本体进行批量烧录。"
                )
                template = (
                    f"请将用户提供的原始文本润色为规范的《{chip} 离线烧录指导》文档, 按以下模板组织内容:\n"
                    "一、烧录工具与软件\n"
                    "二、芯片烧录引脚说明 (引脚定义、顺序、方向)\n"
                    "三、烧录机操作步骤\n"
                    "四、校验方式\n"
                    "五、注意事项"
                )
            out[mode] = {
                "system_role": role,
                "template": template,
                "constraints": [
                    "条理清晰, 分条列出",
                    "保留原文所有关键参数, 不凭空增加内容",
                    "如原文缺少必要信息, 用【待补充】标注",
                    "使用 Markdown 格式输出",
                ],
            }
        return out

    def _parse_constraints(self) -> list:
        """把限制文本按行拆分为列表 (忽略空行)"""
        return [line.strip() for line in self.constraints_edit.toPlainText().splitlines() if line.strip()]

    def _restore_default(self):
        """将当前选择恢复为内置默认模板与限制"""
        defaults = self.cfg.get_factory_defaults().get("text_polish", {}).get("types", {})
        name = self.type_combo.currentText()
        if name == "烧录指导":
            chip = self.chip_combo.currentText()
            mode = self.mode_combo.currentText()
            chip_default = defaults.get("烧录指导", {}).get("chips", {}).get(chip)
            if isinstance(chip_default, dict) and isinstance(chip_default.get(mode), dict):
                cfg = chip_default[mode]
            else:
                cfg = self._generic_chip_defaults(chip).get(mode, {})
        else:
            cfg = defaults.get(name, {})
        if not cfg:
            return
        self.role_edit.setText(cfg.get("system_role", ""))
        self.template_edit.setPlainText(cfg.get("template", ""))
        constraints = cfg.get("constraints", [])
        if isinstance(constraints, str):
            constraints = [constraints]
        self.constraints_edit.setPlainText("\n".join(str(c) for c in constraints))

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
        cfg_types = self.cfg.config.setdefault("text_polish", {}).setdefault("types", {})
        if name == "烧录指导":
            chip = self.chip_combo.currentText()
            mode = self.mode_combo.currentText()
            if not chip or not mode:
                return
            burn = self.polish_types.setdefault("烧录指导", {})
            burn.setdefault("modes", list(DEFAULT_BURN_MODES))
            burn.setdefault("chips", {}).setdefault(chip, {})[mode] = data
            # 写回 config.json
            burn_cfg = cfg_types.setdefault("烧录指导", {})
            burn_cfg.setdefault("modes", list(DEFAULT_BURN_MODES))
            burn_cfg.setdefault("chips", {}).setdefault(chip, {})[mode] = data
        else:
            self.polish_types[name] = data
            cfg_types[name] = data
        self.cfg.save_config()
        self.accept()


class TextPolishPage(QWidget):
    """文本润色页面"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.cfg = ConfigManager(str(app_root() / "config.json"))
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
        subtitle = QLabel(
            "将原始文本润色为规范的工程文档 · 工艺要求 / 测试流程 / 烧录指导 · 模板与限制可在下方⚙️配置"
        )
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
        for text in DEFAULT_TYPE_NAMES:
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

        # 芯片与烧录方式选择行 (仅烧录指导时可见)
        chip_row = QHBoxLayout()
        chip_row.setSpacing(10)
        chip_label = QLabel("芯片厂商:")
        chip_label.setFont(QFont("Microsoft YaHei", 11))
        chip_row.addWidget(chip_label)
        self.chip_combo = QComboBox()
        self.chip_combo.setFont(QFont("Microsoft YaHei", 11))
        self.chip_combo.setMinimumWidth(180)
        self.chip_combo.setStyleSheet(COMBO_STYLE)
        self.chip_combo.currentTextChanged.connect(self._refresh_mode_combo)
        chip_row.addWidget(self.chip_combo)
        mode_label = QLabel("烧录方式:")
        mode_label.setFont(QFont("Microsoft YaHei", 11))
        chip_row.addWidget(mode_label)
        self.mode_combo = QComboBox()
        self.mode_combo.setFont(QFont("Microsoft YaHei", 11))
        self.mode_combo.setMinimumWidth(130)
        self.mode_combo.setStyleSheet(COMBO_STYLE)
        chip_row.addWidget(self.mode_combo)
        chip_row.addStretch()
        self.chip_row_frame = QFrame()
        self.chip_row_frame.setLayout(chip_row)
        self.chip_row_frame.setVisible(False)
        type_layout.addWidget(self.chip_row_frame)
        root.addWidget(type_card)

        self.type_group.buttonClicked.connect(self._on_type_changed)

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
        self.input_edit.setMinimumHeight(130)
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
        self.polish_btn.setStyleSheet(PRIMARY_BTN_STYLE)
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
        self.result_browser.setMinimumHeight(150)
        self.result_browser.setStyleSheet(
            "QTextBrowser { border: 1px solid #DCDFE6; border-radius: 8px;"
            "padding: 10px; background: white; }"
            "QTextBrowser a { color: #409EFF; }"
        )
        result_layout.addWidget(self.result_browser, 1)
        root.addWidget(result_card, 1)

    # ==================== 模板与限制配置 ====================
    def _load_polish_types(self) -> dict:
        """从 config.json → text_polish.types 加载配置, 与出厂默认深度合并"""
        defaults = self.cfg.get_factory_defaults().get("text_polish", {}).get("types", {})
        cfg_types = self.cfg.config.get("text_polish", {}).get("types", {})
        if not isinstance(cfg_types, dict) or not cfg_types:
            return copy.deepcopy(defaults)
        types = {}
        for name in DEFAULT_TYPE_NAMES:
            types[name] = _deep_merge(defaults.get(name, {}), cfg_types.get(name, {}))
        for name, item in cfg_types.items():
            if name not in types and isinstance(item, dict):
                types[name] = copy.deepcopy(item)
        return types

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

    # ==================== 选择状态 ====================
    def _selected_type(self) -> str:
        btn = self.type_group.checkedButton()
        return btn.text() if btn else DEFAULT_TYPE_NAMES[0]

    def _selected_chip(self) -> str:
        return self.chip_combo.currentText() if self.chip_combo.count() else ""

    def _selected_mode(self) -> str:
        return self.mode_combo.currentText() if self.mode_combo.count() else ""

    def _on_type_changed(self, *_):
        """切换文档类型: 烧录指导时显示芯片/烧录方式选择行"""
        is_burn = self._selected_type() == "烧录指导"
        self.chip_row_frame.setVisible(is_burn)
        if is_burn:
            self._refresh_chip_combo()

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
        self._refresh_mode_combo()

    def _refresh_mode_combo(self, *_):
        burn = self.polish_types.get("烧录指导", {})
        chip = self.chip_combo.currentText()
        modes = burn.get("modes") or list(DEFAULT_BURN_MODES)
        chip_cfg = burn.get("chips", {}).get(chip, {})
        available = [m for m in modes if isinstance(chip_cfg.get(m), dict)] or list(modes)
        current = self.mode_combo.currentText()
        self.mode_combo.blockSignals(True)
        self.mode_combo.clear()
        self.mode_combo.addItems(available)
        if current in available:
            self.mode_combo.setCurrentText(current)
        self.mode_combo.blockSignals(False)

    def _resolve_type_cfg(self):
        """解析当前选择的模板配置 (烧录指导取 芯片×烧录方式)"""
        doc_type = self._selected_type()
        cfg = self.polish_types.get(doc_type)
        if not isinstance(cfg, dict):
            return None
        if doc_type == "烧录指导":
            chip = self._selected_chip()
            mode = self._selected_mode()
            if not chip or not mode:
                return None
            return cfg.get("chips", {}).get(chip, {}).get(mode)
        return cfg

    def _doc_title(self) -> str:
        """当前生成的文档标题"""
        doc_type = self._selected_type()
        if doc_type == "烧录指导":
            return f"{self._selected_chip()} {self._selected_mode()}指导"
        return doc_type

    # ==================== 动作 ====================
    def open_config_dialog(self):
        """打开模板与限制配置窗口"""
        dlg = TextPolishConfigDialog(self.cfg, self.polish_types, self)
        if dlg.exec():
            # 配置可能被修改 (含新增芯片), 重新加载以同步界面
            self.polish_types = self._load_polish_types()
            if self._selected_type() == "烧录指导":
                self._refresh_chip_combo()
            self._set_status("✅ 配置已保存, 新模板与限制将在下次润色时生效。", "#67C23A")

    def polish(self):
        """调用 DeepSeek 按所选类型润色文本"""
        doc_type = self._selected_type()
        type_cfg = self._resolve_type_cfg()
        if type_cfg is None:
            if doc_type == "烧录指导":
                self._set_status(
                    "⚠ 当前芯片/烧录方式未配置模板, 请点击「⚙️ 模板配置」为芯片设置模板。",
                    "#E6A23C",
                )
            else:
                self._set_status(
                    "⚠ 该文档类型未配置模板与限制, 请点击「⚙️ 模板配置」。",
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

        doc_title = self._doc_title()
        self.polish_btn.setEnabled(False)
        self._set_status(f"⏳ 正在按「{doc_title}」润色, 请稍候 (约 10~30 秒)…", "#409EFF")
        self.result_browser.setPlainText("")

        prompt = f"请将以下原始文本润色为规范的《{doc_title}》文档:\n\n{raw}"
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

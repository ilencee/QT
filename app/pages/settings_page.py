"""
系统设置页面

功能:
- AI 服务设置: 支持国内多家知名大模型 (DeepSeek / 通义千问 / 智谱 GLM / Kimi /
  腾讯混元 / 百度千帆 / 火山豆包), 均可选服务商后自动带出 Base URL 与模型列表
- 配置 API Key / Base URL / 模型 / Temperature / Max Tokens
- 测试连接: 用表单当前值直接发一个最小请求, 验证 Key 与网络是否可用
- 保存设置: 写入 config.json → power_conversion.api, 文本润色/功率变换页面立即生效
- 恢复默认: 恢复出厂默认参数并保存
- 提供获取 API Key 的步骤说明

说明:
- 所有服务商均走 OpenAI 兼容 /chat/completions 接口, 单 API Key (Bearer) 模式
- 配置存放在本机 config.json (exe 同级或项目根目录), 不会上传到任何服务器
- 保存后同路径 ConfigManager 为共享实例, 其他页面无需重启即可用新配置
"""

import os
import time
import webbrowser

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QFont
from PyQt6.QtWidgets import (
    QCheckBox, QComboBox, QDoubleSpinBox, QFrame, QGridLayout, QHBoxLayout, QLabel,
    QLineEdit, QPushButton, QScrollArea, QSpinBox, QVBoxLayout, QWidget,
)

from app.core.config_manager import ConfigManager, app_root
from app.core.deepseek_client import (
    DEFAULT_BASE_URL, DEFAULT_MODEL, DeepSeekThread, load_api_config,
)
from app.core.tencent_docs import (
    TencentDocsClient, TencentDocsThread, build_config_backup_html,
    parse_jwt_payload,
)

TENCENT_DOCS_HOME = "https://docs.qq.com/open/document/app/"

CUSTOM_PROVIDER = "自定义"

# 国内主流大模型服务商预设 (OpenAI 兼容接口, 单 API Key 模式)
# 切换服务商自动带出 base_url 与常用模型列表; 模型也支持手动输入
PROVIDERS = {
    "DeepSeek": {
        "base_url": "https://api.deepseek.com/chat/completions",
        "models": ["deepseek-chat", "deepseek-reasoner"],
        "website": "https://platform.deepseek.com",
        "note": "注册→充值→API Keys",
    },
    "阿里云通义千问": {
        "base_url": "https://dashscope.aliyuncs.com/compatible-mode/v1/chat/completions",
        "models": ["qwen-max", "qwen-plus", "qwen-turbo", "qwen-long"],
        "website": "https://bailian.console.aliyun.com",
        "note": "百炼控制台→API-KEY 管理",
    },
    "智谱 GLM": {
        "base_url": "https://open.bigmodel.cn/api/paas/v4/chat/completions",
        "models": ["glm-4-plus", "glm-4-air", "glm-4-flash", "glm-4-long"],
        "website": "https://open.bigmodel.cn",
        "note": "开放平台→API Keys",
    },
    "月之暗面 Kimi": {
        "base_url": "https://api.moonshot.cn/v1/chat/completions",
        "models": ["kimi-latest", "moonshot-v1-8k", "moonshot-v1-32k", "moonshot-v1-128k"],
        "website": "https://platform.moonshot.cn",
        "note": "开放平台→API Key",
    },
    "腾讯混元": {
        "base_url": "https://api.hunyuan.cloud.tencent.com/v1/chat/completions",
        "models": ["hunyuan-turbo", "hunyuan-pro", "hunyuan-standard", "hunyuan-lite"],
        "website": "https://console.cloud.tencent.com/hunyuan",
        "note": "腾讯云控制台→API 密钥管理",
    },
    "百度千帆": {
        "base_url": "https://qianfan.baidubce.com/v2/chat/completions",
        "models": ["ernie-4.0-8k", "ernie-4.0-turbo-8k", "ernie-3.5-8k", "ernie-speed-8k", "ernie-lite-8k"],
        "website": "https://console.bce.baidu.com/qianfan",
        "note": "千帆控制台→API Key",
    },
    "火山豆包": {
        "base_url": "https://ark.cn-beijing.volces.com/api/v3/chat/completions",
        "models": ["doubao-1-5-pro-32k", "doubao-1-5-lite-32k", "doubao-pro-32k", "doubao-lite-32k"],
        "website": "https://console.volcengine.com/ark",
        "note": "火山方舟→API Key 管理",
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
INPUT_STYLE = (
    "QLineEdit { border: 1px solid #DCDFE6; border-radius: 6px;"
    "padding: 6px 10px; background: white; }"
    "QLineEdit:focus { border-color: #409EFF; }"
)
SPIN_STYLE = (
    "QSpinBox, QDoubleSpinBox { border: 1px solid #DCDFE6; border-radius: 6px;"
    "padding: 4px 8px; background: white; }"
    "QSpinBox:focus, QDoubleSpinBox:focus { border-color: #409EFF; }"
)


class SettingsPage(QWidget):
    """系统设置页面"""

    def __init__(self, parent=None, on_visibility_changed=None, nav_items=None):
        super().__init__(parent)
        self.cfg = ConfigManager(str(app_root() / "config.json"))
        self.ai_thread = None
        self.td_thread = None  # 腾讯文档同步线程
        # 栏目显隐回调 (主窗口传入, 勾选变化即时刷新导航/首页) 与栏目数据
        self._on_visibility_changed = on_visibility_changed
        self._nav_items = nav_items if nav_items else self._default_nav_items()
        self._vis_checks = {}
        self._setup_ui()
        self._load_from_config()

    @staticmethod
    def _default_nav_items():
        """兜底栏目数据 (无主窗口传入时, 如诊断脚本直接实例化)"""
        return [
            ("🏠", "首页概览"), ("🔌", "串口调试"), ("📄", "文本润色"),
            ("💾", "烧录软件"), ("🔧", "硬件工具箱"),
            ("📚", "常识查询"), ("⚙️", "系统设置"),
        ]

    def _locked_indexes(self):
        """锁定不可隐藏的栏目索引: 首页(0) + 系统设置(末位)"""
        return {0, len(self._nav_items) - 1}

    # ==================== UI 构建 ====================
    def _setup_ui(self):
        # 外层滚动区: 小窗口/小屏时可滚动, 避免内容被裁剪
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setStyleSheet("QScrollArea { background: transparent; border: none; }")
        scroll.viewport().setAutoFillBackground(False)
        content = QWidget()
        scroll.setWidget(content)

        root = QVBoxLayout(content)
        root.setContentsMargins(24, 20, 24, 20)
        root.setSpacing(16)

        # 标题区
        title = QLabel("⚙️ 系统设置")
        title.setFont(QFont("Microsoft YaHei", 20, QFont.Weight.Bold))
        root.addWidget(title)
        subtitle = QLabel(
            "配置 AI 服务 (DeepSeek API) 等全局选项 · 保存后立即对所有页面生效"
        )
        subtitle.setFont(QFont("Microsoft YaHei", 10))
        subtitle.setStyleSheet("color: #909399; background: transparent; border: none;")
        root.addWidget(subtitle)

        # 两栏布局: 左列主表单 (自适应拉伸) + 右列辅助信息 (按内容宽度)
        columns = QHBoxLayout()
        columns.setSpacing(16)
        left_col = QVBoxLayout()
        left_col.setSpacing(16)
        right_col = QVBoxLayout()
        right_col.setSpacing(16)

        # 1. AI 服务设置卡片
        api_card = QFrame()
        api_card.setStyleSheet(CARD_STYLE)
        api_layout = QVBoxLayout(api_card)
        api_layout.setContentsMargins(16, 12, 16, 12)
        api_layout.setSpacing(10)

        api_title = QLabel("🤖 AI 服务设置")
        api_title.setStyleSheet(SECTION_TITLE_STYLE)
        api_layout.addWidget(api_title)

        api_hint = QLabel(
            "支持 DeepSeek / 通义千问 / 智谱 GLM / Kimi / 混元 / 千帆 / 豆包等主流大模型,"
            " 文本润色、功率变换页面的 AI 分析均使用这里的配置。"
            "API Key 仅保存在本机 config.json, 不会上传。"
        )
        api_hint.setFont(QFont("Microsoft YaHei", 10))
        api_hint.setStyleSheet("color: #909399; background: transparent; border: none;")
        api_hint.setWordWrap(True)
        api_layout.addWidget(api_hint)

        form = QGridLayout()
        form.setHorizontalSpacing(12)
        form.setVerticalSpacing(10)

        # 服务商
        provider_label = QLabel("服务商:")
        provider_label.setFont(QFont("Microsoft YaHei", 11))
        form.addWidget(provider_label, 0, 0)
        self.provider_combo = QComboBox()
        self.provider_combo.setFont(QFont("Microsoft YaHei", 11))
        self.provider_combo.setCursor(Qt.CursorShape.PointingHandCursor)
        self.provider_combo.addItem(CUSTOM_PROVIDER)
        self.provider_combo.addItems(list(PROVIDERS.keys()))
        self.provider_combo.setStyleSheet(
            "QComboBox { border: 1px solid #DCDFE6; border-radius: 6px;"
            "padding: 5px 10px; background: white; }"
        )
        self.provider_combo.currentTextChanged.connect(self._on_provider_changed)
        form.addWidget(self.provider_combo, 0, 1, 1, 2)

        # API Key
        key_label = QLabel("API Key:")
        key_label.setFont(QFont("Microsoft YaHei", 11))
        form.addWidget(key_label, 1, 0)
        self.key_edit = QLineEdit()
        self.key_edit.setFont(QFont("Microsoft YaHei", 11))
        self.key_edit.setPlaceholderText("sk-xxxxxxxx…")
        self.key_edit.setEchoMode(QLineEdit.EchoMode.Password)
        self.key_edit.setStyleSheet(INPUT_STYLE)
        form.addWidget(self.key_edit, 1, 1)
        self.show_key_check = QCheckBox("显示")
        self.show_key_check.setFont(QFont("Microsoft YaHei", 10))
        self.show_key_check.setCursor(Qt.CursorShape.PointingHandCursor)
        self.show_key_check.toggled.connect(self._toggle_key_visible)
        form.addWidget(self.show_key_check, 1, 2)

        # Base URL
        url_label = QLabel("Base URL:")
        url_label.setFont(QFont("Microsoft YaHei", 11))
        form.addWidget(url_label, 2, 0)
        self.base_url_edit = QLineEdit()
        self.base_url_edit.setFont(QFont("Microsoft YaHei", 11))
        self.base_url_edit.setPlaceholderText(DEFAULT_BASE_URL)
        self.base_url_edit.setStyleSheet(INPUT_STYLE)
        self.base_url_edit.textChanged.connect(self._on_base_url_changed)
        form.addWidget(self.base_url_edit, 2, 1, 1, 2)

        # 模型 (可编辑下拉, 支持手动输入)
        model_label = QLabel("模型:")
        model_label.setFont(QFont("Microsoft YaHei", 11))
        form.addWidget(model_label, 3, 0)
        self.model_combo = QComboBox()
        self.model_combo.setFont(QFont("Microsoft YaHei", 11))
        self.model_combo.setEditable(True)
        self.model_combo.setInsertPolicy(QComboBox.InsertPolicy.NoInsert)
        self.model_combo.setPlaceholderText(DEFAULT_MODEL)
        self.model_combo.setStyleSheet(
            "QComboBox { border: 1px solid #DCDFE6; border-radius: 6px;"
            "padding: 5px 10px; background: white; }"
            "QComboBox:focus { border-color: #409EFF; }"
        )
        self.model_combo.setToolTip("切换服务商自动带出常用模型, 也可手动输入新模型名")
        form.addWidget(self.model_combo, 3, 1, 1, 2)

        # Temperature + Max Tokens 并排一行 (压缩表单高度)
        pair_row = QHBoxLayout()
        pair_row.setSpacing(12)
        temp_label = QLabel("Temperature:")
        temp_label.setFont(QFont("Microsoft YaHei", 11))
        pair_row.addWidget(temp_label)
        self.temp_spin = QDoubleSpinBox()
        self.temp_spin.setRange(0.0, 2.0)
        self.temp_spin.setSingleStep(0.1)
        self.temp_spin.setDecimals(1)
        self.temp_spin.setValue(0.7)
        self.temp_spin.setStyleSheet(SPIN_STYLE)
        self.temp_spin.setToolTip("越低越严谨, 越高越自由 (0~2)")
        pair_row.addWidget(self.temp_spin, 1)
        tokens_label = QLabel("Max Tokens:")
        tokens_label.setFont(QFont("Microsoft YaHei", 11))
        pair_row.addWidget(tokens_label)
        self.tokens_spin = QSpinBox()
        self.tokens_spin.setRange(1, 8192)
        self.tokens_spin.setSingleStep(100)
        self.tokens_spin.setValue(1500)
        self.tokens_spin.setStyleSheet(SPIN_STYLE)
        self.tokens_spin.setToolTip("单次回复最大 token 数")
        pair_row.addWidget(self.tokens_spin, 1)
        form.addLayout(pair_row, 4, 0, 1, 3)

        form.setColumnStretch(1, 1)
        api_layout.addLayout(form)

        # 按钮行
        btn_row = QHBoxLayout()
        btn_row.setSpacing(12)
        self.test_btn = QPushButton("🔌 测试连接")
        self.test_btn.setMinimumHeight(36)
        self.test_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.test_btn.setStyleSheet(SECONDARY_BTN_STYLE)
        self.test_btn.clicked.connect(self.test_connection)
        btn_row.addWidget(self.test_btn)

        self.save_btn = QPushButton("💾 保存设置")
        self.save_btn.setMinimumHeight(36)
        self.save_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.save_btn.setStyleSheet(PRIMARY_BTN_STYLE)
        self.save_btn.clicked.connect(self.save_settings)
        btn_row.addWidget(self.save_btn)

        self.restore_btn = QPushButton("♻️ 恢复默认")
        self.restore_btn.setMinimumHeight(36)
        self.restore_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.restore_btn.setStyleSheet(SECONDARY_BTN_STYLE)
        self.restore_btn.clicked.connect(self.restore_defaults)
        btn_row.addWidget(self.restore_btn)

        btn_row.addStretch()
        api_layout.addLayout(btn_row)

        self.status_label = QLabel("")
        self.status_label.setWordWrap(True)
        self.status_label.setStyleSheet("color: #909399; background: transparent; border: none;")
        api_layout.addWidget(self.status_label)

        left_col.addWidget(api_card)

        # 1.5 栏目显示卡片 (隐藏/显示左侧导航栏目, 勾选即时生效并持久化)
        vis_card = QFrame()
        vis_card.setStyleSheet(CARD_STYLE)
        vis_layout = QVBoxLayout(vis_card)
        vis_layout.setContentsMargins(16, 12, 16, 12)
        vis_layout.setSpacing(8)

        vis_title = QLabel("📑 栏目显示")
        vis_title.setStyleSheet(SECTION_TITLE_STYLE)
        vis_layout.addWidget(vis_title)

        vis_hint = QLabel(
            "勾选要显示的栏目, 取消勾选即从左侧导航与首页快捷卡片中隐藏。\n"
            "首页概览 / 系统设置为固定栏目, 不可隐藏 (防止失去管理入口)。"
        )
        vis_hint.setFont(QFont("Microsoft YaHei", 10))
        vis_hint.setStyleSheet("color: #909399; background: transparent; border: none;")
        vis_hint.setWordWrap(True)
        vis_layout.addWidget(vis_hint)

        vis_grid = QGridLayout()
        vis_grid.setHorizontalSpacing(24)
        vis_grid.setVerticalSpacing(6)
        locked_idx = self._locked_indexes()
        for idx, (icon, name) in enumerate(self._nav_items):
            cb = QCheckBox(f"{icon}  {name}")
            cb.setFont(QFont("Microsoft YaHei", 11))
            cb.setCursor(Qt.CursorShape.PointingHandCursor)
            if idx in locked_idx:
                cb.setEnabled(False)
                cb.setText(f"{icon}  {name}  （固定显示）")
            cb.toggled.connect(
                lambda checked, i=idx, nm=name: self._on_vis_toggled(i, nm, checked)
            )
            self._vis_checks[idx] = cb
            row, col = divmod(idx, 2)
            vis_grid.addWidget(cb, row, col)
        vis_layout.addLayout(vis_grid)
        left_col.addWidget(vis_card)

        # 2. 腾讯文档同步卡片 (防丢失备份)
        td_card = QFrame()
        td_card.setStyleSheet(CARD_STYLE)
        td_layout = QVBoxLayout(td_card)
        td_layout.setContentsMargins(16, 12, 16, 12)
        td_layout.setSpacing(10)

        td_title = QLabel("☁ 腾讯文档同步 (防止配置/模板丢失)")
        td_title.setStyleSheet(SECTION_TITLE_STYLE)
        td_layout.addWidget(td_title)

        td_hint = QLabel(
            "一键把全部配置 (AI 设置、烧录指导模板等) 备份为腾讯在线文档, "
            "每次备份生成新文档, 旧版本自动保留, 天然形成版本历史。"
        )
        td_hint.setFont(QFont("Microsoft YaHei", 10))
        td_hint.setStyleSheet("color: #606266; background: transparent; border: none;")
        td_hint.setWordWrap(True)
        td_layout.addWidget(td_hint)

        td_reg_btn = QPushButton("📄 打开腾讯文档开放平台 (注册/创建应用)")
        td_reg_btn.setMinimumHeight(30)
        td_reg_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        td_reg_btn.setStyleSheet(SECONDARY_BTN_STYLE)
        td_reg_btn.clicked.connect(
            lambda: webbrowser.open("https://docs.qq.com/open/document/app/get_started.html")
        )
        td_layout.addWidget(td_reg_btn)

        # 凭证方式: 二选一, 切换时只显示对应输入区 (默认 Access Token, 界面更简洁)
        td_mode_row = QHBoxLayout()
        td_mode_row.setSpacing(8)
        mode_label = QLabel("凭证方式:")
        mode_label.setFont(QFont("Microsoft YaHei", 11))
        td_mode_row.addWidget(mode_label)
        self.td_mode_combo = QComboBox()
        self.td_mode_combo.addItem("① Access Token（推荐，粘贴即用）")
        self.td_mode_combo.addItem("② Client ID + Client Secret")
        self.td_mode_combo.setCursor(Qt.CursorShape.PointingHandCursor)
        self.td_mode_combo.setStyleSheet(
            "QComboBox { border: 1px solid #DCDFE6; border-radius: 6px;"
            "padding: 5px 10px; background: white; }"
        )
        self.td_mode_combo.currentIndexChanged.connect(self._td_toggle_mode)
        td_mode_row.addWidget(self.td_mode_combo, 1)
        td_layout.addLayout(td_mode_row)

        # 模式①: Access Token 单行
        self.td_token_box = QWidget()
        token_layout = QHBoxLayout(self.td_token_box)
        token_layout.setContentsMargins(0, 0, 0, 0)
        token_layout.setSpacing(8)
        token_label = QLabel("Access Token:")
        token_label.setFont(QFont("Microsoft YaHei", 11))
        token_layout.addWidget(token_label)
        self.td_access_token = QLineEdit()
        self.td_access_token.setEchoMode(QLineEdit.EchoMode.Password)
        self.td_access_token.setFont(QFont("Microsoft YaHei", 11))
        self.td_access_token.setPlaceholderText(
            "应用账号令牌 (JWT), 粘贴后自动识别 Client ID / 有效期"
        )
        self.td_access_token.setStyleSheet(INPUT_STYLE)
        token_layout.addWidget(self.td_access_token, 1)
        self.td_token_visible = QCheckBox("显示")
        self.td_token_visible.setStyleSheet("background: transparent; border: none;")
        self.td_token_visible.setCursor(Qt.CursorShape.PointingHandCursor)
        self.td_token_visible.toggled.connect(
            lambda on: self.td_access_token.setEchoMode(
                QLineEdit.EchoMode.Normal if on else QLineEdit.EchoMode.Password
            )
        )
        token_layout.addWidget(self.td_token_visible)
        td_layout.addWidget(self.td_token_box)

        # 模式②: Client ID / Client Secret / Open ID
        self.td_cred_box = QWidget()
        cred_layout = QGridLayout(self.td_cred_box)
        cred_layout.setContentsMargins(0, 0, 0, 0)
        cred_layout.setSpacing(8)
        cred_layout.setColumnStretch(1, 1)
        cred_layout.addWidget(QLabel("Client ID:"), 0, 0)
        self.td_client_id = QLineEdit()
        self.td_client_id.setFont(QFont("Microsoft YaHei", 11))
        self.td_client_id.setPlaceholderText("应用审核通过后的 Client ID")
        self.td_client_id.setStyleSheet(INPUT_STYLE)
        cred_layout.addWidget(self.td_client_id, 0, 1)
        cred_layout.addWidget(QLabel("Client Secret:"), 1, 0)
        self.td_client_secret = QLineEdit()
        self.td_client_secret.setEchoMode(QLineEdit.EchoMode.Password)
        self.td_client_secret.setFont(QFont("Microsoft YaHei", 11))
        self.td_client_secret.setPlaceholderText("应用审核通过后的 Client Secret")
        self.td_client_secret.setStyleSheet(INPUT_STYLE)
        cred_layout.addWidget(self.td_client_secret, 1, 1)
        self.td_secret_visible = QCheckBox("显示")
        self.td_secret_visible.setStyleSheet("background: transparent; border: none;")
        self.td_secret_visible.setCursor(Qt.CursorShape.PointingHandCursor)
        self.td_secret_visible.toggled.connect(
            lambda on: self.td_client_secret.setEchoMode(
                QLineEdit.EchoMode.Normal if on else QLineEdit.EchoMode.Password
            )
        )
        cred_layout.addWidget(self.td_secret_visible, 1, 2)
        cred_layout.addWidget(QLabel("Open ID:"), 2, 0)
        self.td_open_id = QLineEdit()
        self.td_open_id.setFont(QFont("Microsoft YaHei", 11))
        self.td_open_id.setPlaceholderText(
            "可选; 粘贴 Access Token 时自动识别, 一般无需填写"
        )
        self.td_open_id.setStyleSheet(INPUT_STYLE)
        cred_layout.addWidget(self.td_open_id, 2, 1)
        td_layout.addWidget(self.td_cred_box)

        td_btn_row = QHBoxLayout()
        td_btn_row.setSpacing(10)
        self.td_test_btn = QPushButton("🔌 测试连接")
        self.td_test_btn.setMinimumHeight(32)
        self.td_test_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.td_test_btn.setStyleSheet(SECONDARY_BTN_STYLE)
        self.td_test_btn.clicked.connect(self._td_test)
        td_btn_row.addWidget(self.td_test_btn)
        self.td_backup_btn = QPushButton("☁ 一键备份配置到腾讯文档")
        self.td_backup_btn.setMinimumHeight(32)
        self.td_backup_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.td_backup_btn.setStyleSheet(PRIMARY_BTN_STYLE)
        self.td_backup_btn.clicked.connect(self._td_backup)
        td_btn_row.addWidget(self.td_backup_btn)
        td_btn_row.addStretch()
        td_layout.addLayout(td_btn_row)

        self.td_status = QLabel("")
        self.td_status.setWordWrap(True)
        self.td_status.setStyleSheet(
            "color: #909399; background: transparent; border: none;"
        )
        td_layout.addWidget(self.td_status)

        self.td_last_url = QLabel("")
        self.td_last_url.setWordWrap(True)
        self.td_last_url.setTextFormat(Qt.TextFormat.RichText)
        self.td_last_url.setOpenExternalLinks(True)
        self.td_last_url.setStyleSheet(
            "color: #409EFF; background: transparent; border: none;"
        )
        td_layout.addWidget(self.td_last_url)

        left_col.addWidget(td_card)

        # 3. 服务商说明卡片 (随所选服务商更新)
        guide_card = QFrame()
        guide_card.setStyleSheet(CARD_STYLE)
        guide_layout = QVBoxLayout(guide_card)
        guide_layout.setContentsMargins(16, 12, 16, 12)
        guide_layout.setSpacing(8)

        guide_title = QLabel("🔑 如何获取 API Key")
        guide_title.setStyleSheet(SECTION_TITLE_STYLE)
        guide_layout.addWidget(guide_title)

        self.guide_text = QLabel("")
        self.guide_text.setFont(QFont("Microsoft YaHei", 10))
        self.guide_text.setStyleSheet("color: #606266; background: transparent; border: none;")
        self.guide_text.setWordWrap(True)
        guide_layout.addWidget(self.guide_text)
        guide_card.setMinimumWidth(280)
        right_col.addWidget(guide_card)

        # 4. 配置信息卡片 → 右侧列
        info_card = QFrame()
        info_card.setStyleSheet(CARD_STYLE)
        info_layout = QVBoxLayout(info_card)
        info_layout.setContentsMargins(16, 12, 16, 12)
        info_layout.setSpacing(10)

        info_title = QLabel("📁 配置信息")
        info_title.setStyleSheet(SECTION_TITLE_STYLE)
        info_layout.addWidget(info_title)

        info_row = QHBoxLayout()
        info_row.setSpacing(10)
        path_label = QLabel("配置文件:")
        path_label.setFont(QFont("Microsoft YaHei", 11))
        info_row.addWidget(path_label)
        self.path_value = QLabel(str(self.cfg.config_file))
        self.path_value.setFont(QFont("Microsoft YaHei", 10))
        self.path_value.setStyleSheet(
            "color: #606266; background: #F5F7FA; border-radius: 4px;"
            "padding: 4px 8px; border: none;"
        )
        self.path_value.setWordWrap(True)
        info_row.addWidget(self.path_value, 1)
        open_btn = QPushButton("打开所在文件夹")
        open_btn.setMinimumHeight(30)
        open_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        open_btn.setStyleSheet(SECONDARY_BTN_STYLE)
        open_btn.clicked.connect(self._open_config_folder)
        info_row.addWidget(open_btn)
        info_layout.addLayout(info_row)
        info_card.setMinimumWidth(280)
        right_col.addWidget(info_card)

        # 右列底部弹性占位 (卡片顶对齐, 不拉伸)
        right_col.addStretch()

        # 组装两栏: 左列自适应拉伸, 右列按内容宽度
        left_col.addStretch()
        columns.addLayout(left_col, 1)
        columns.addLayout(right_col, 0)
        root.addLayout(columns)

        # 整个设置页装入滚动区
        page_layout = QVBoxLayout(self)
        page_layout.setContentsMargins(0, 0, 0, 0)
        page_layout.addWidget(scroll)

    # ==================== 数据加载 ====================
    def _load_from_config(self):
        """把当前配置加载到表单 (与 load_api_config 同一套防御式解析)"""
        api = load_api_config(self.cfg)
        section = self.cfg.config.get("power_conversion", {}).get("api", {})
        saved_provider = str(section.get("provider", "") or "")

        self.key_edit.setText(api["api_key"])
        self.base_url_edit.setText(api["base_url"])
        self.temp_spin.setValue(api["temperature"])
        self.tokens_spin.setValue(api["max_tokens"])

        # 服务商: 优先用保存的 provider, 其次按 base_url 匹配, 否则自定义
        provider = saved_provider if saved_provider in PROVIDERS else ""
        if not provider:
            provider = self._provider_for_base_url(api["base_url"])
        if not provider:
            provider = CUSTOM_PROVIDER
        self.provider_combo.setCurrentText(provider)

        # 模型: 有值用保存值, 否则用该服务商第一个推荐模型
        self._refresh_model_combo(provider)
        model = api["model"]
        if not model:
            models = PROVIDERS[provider]["models"] if provider in PROVIDERS else []
            model = models[0] if models else DEFAULT_MODEL
        self.model_combo.setCurrentText(model)
        self._update_guide_text(provider)

        # 腾讯文档同步凭证
        td = self.cfg.config.get("tencent_docs", {}) or {}
        self.td_access_token.setText(str(td.get("access_token", "") or ""))
        self.td_client_id.setText(str(td.get("client_id", "") or ""))
        self.td_client_secret.setText(str(td.get("client_secret", "") or ""))
        self.td_open_id.setText(str(td.get("open_id", "") or ""))
        # 凭证模式: 已有 Access Token 或没有任何凭证 → Access Token 模式, 否则 Client 模式
        has_cred = bool(
            str(td.get("client_id", "") or "") or str(td.get("client_secret", "") or "")
        )
        mode = 0 if str(td.get("access_token", "") or "") or not has_cred else 1
        self.td_mode_combo.blockSignals(True)
        self.td_mode_combo.setCurrentIndex(mode)
        self.td_mode_combo.blockSignals(False)
        self._td_toggle_mode(mode)
        last_url = str(td.get("last_url", "") or "")
        if last_url:
            self.td_last_url.setText(
                f"最近一次备份: <a href='{last_url}'>{last_url}</a>"
            )

        # 栏目显示: 按已保存隐藏配置设置勾选态 (blockSignals 防止加载阶段误触发保存回调)
        hidden = set(self.cfg.get_window_config().get("hidden_pages", []) or [])
        locked_idx = self._locked_indexes()
        for i, (_, name) in enumerate(self._nav_items):
            cb = self._vis_checks.get(i)
            if cb is None:
                continue
            if i in locked_idx:
                cb.setChecked(True)
            else:
                cb.blockSignals(True)
                cb.setChecked(name not in hidden)
                cb.blockSignals(False)

    # ==================== 栏目显隐 ====================
    def _on_vis_toggled(self, index, name, checked):
        """栏目勾选变化: 收集未勾选栏目 → 写配置 → 回调主窗口即时刷新"""
        hidden = []
        locked_idx = self._locked_indexes()
        for i, (_, nm) in enumerate(self._nav_items):
            if i in locked_idx:
                continue  # 锁定栏目恒显示
            cb = self._vis_checks.get(i)
            if cb is not None and not cb.isChecked():
                hidden.append(nm)
        self._save_hidden(hidden)

    def _save_hidden(self, hidden):
        """持久化 window.hidden_pages 并回调主窗口应用显隐"""
        try:
            self.cfg.set_value("window.hidden_pages", sorted(hidden))
            self.cfg.save_config()
        except Exception:
            pass
        if self._on_visibility_changed is not None:
            self._on_visibility_changed(hidden)

    def _form_api(self) -> dict:
        """从表单读取当前值 (与配置文件格式一致)"""
        provider = self.provider_combo.currentText()
        base_url = self.base_url_edit.text().strip() or DEFAULT_BASE_URL
        # 若当前 base_url 已匹配某厂商预设, 即使下拉显示"自定义"也记为厂商名
        provider = self._provider_for_base_url(base_url) or provider
        return {
            "api_key": self.key_edit.text().strip(),
            "base_url": base_url,
            "model": self.model_combo.currentText().strip() or DEFAULT_MODEL,
            "provider": provider,
            "temperature": self.temp_spin.value(),
            "max_tokens": self.tokens_spin.value(),
        }

    # ==================== 服务商联动 ====================
    def _on_provider_changed(self, provider):
        """切换服务商: 自动带出该厂商的 Base URL 与模型列表"""
        if provider in PROVIDERS:
            self.base_url_edit.blockSignals(True)
            self.base_url_edit.setText(PROVIDERS[provider]["base_url"])
            self.base_url_edit.blockSignals(False)
        self._refresh_model_combo(provider)
        self._update_guide_text(provider)

    def _on_base_url_changed(self, text):
        """用户手动改 Base URL: 若匹配某厂商预设则同步服务商下拉与说明卡片"""
        text = text.strip()
        provider = self._provider_for_base_url(text) if text else ""
        target = provider if provider else CUSTOM_PROVIDER
        if self.provider_combo.currentText() != target:
            self.provider_combo.blockSignals(True)
            self.provider_combo.setCurrentText(target)
            self.provider_combo.blockSignals(False)
        self._update_guide_text(target)

    def _provider_for_base_url(self, base_url: str) -> str:
        """按 Base URL 反查服务商, 匹配不到返回空串"""
        for name, presets in PROVIDERS.items():
            if base_url and base_url.strip("/") == presets["base_url"].strip("/"):
                return name
        return ""

    def _refresh_model_combo(self, provider):
        """按服务商刷新模型候选列表; 当前模型不在新列表时自动换成该厂商首个模型"""
        current = self.model_combo.currentText()
        models = list(PROVIDERS[provider]["models"]) if provider in PROVIDERS else []
        self.model_combo.clear()
        self.model_combo.addItems(models)
        if current in models:
            self.model_combo.setCurrentText(current)
        elif models:
            self.model_combo.setCurrentText(models[0])

    def _update_guide_text(self, provider):
        """刷新"如何获取 API Key"说明卡片内容"""
        if provider in PROVIDERS:
            presets = PROVIDERS[provider]
            self.guide_text.setText(
                f"1. 打开「{provider}」官网/控制台: {presets['website']}\n"
                f"2. {presets['note']} → 创建新 Key, 复制密钥字符串\n"
                f"3. 粘贴到上方「API Key」输入框, 点击「🔌 测试连接」验证是否可用\n"
                f"4. Base URL 与模型已自动带出, 也可按需修改\n"
                f"\n"
                f"提示: API Key 是账号凭证, 请勿泄露给他人。本软件仅保存在本机配置文件。"
            )
        else:
            self.guide_text.setText(
                "已选择自定义服务商: 请根据对应平台文档填写 Base URL 与模型名,"
                " 并保证接口为 OpenAI 兼容的 /chat/completions 格式。\n"
                "\n"
                "提示: API Key 是账号凭证, 请勿泄露给他人。本软件仅保存在本机配置文件。"
            )

    # ==================== 动作 ====================
    def save_settings(self):
        """保存到 config.json → power_conversion.api (文本润色/功率变换页共用)"""
        api = self._form_api()
        if not api["api_key"]:
            self._set_status(
                "⚠ 尚未填写 API Key, 请先获取并粘贴 (也可保存空值, 之后再补)。",
                "#E6A23C",
            )
        section = self.cfg.config.setdefault("power_conversion", {}).setdefault("api", {})
        section.update(api)
        td_section = self.cfg.config.setdefault("tencent_docs", {})
        td_section["access_token"] = self.td_access_token.text().strip()
        td_section["client_id"] = self.td_client_id.text().strip()
        td_section["client_secret"] = self.td_client_secret.text().strip()
        td_section["open_id"] = self.td_open_id.text().strip()
        ok = self.cfg.save_config()
        if ok:
            self._set_status(
                "✅ 已保存。文本润色 / 功率变换页面下次请求立即使用新配置。",
                "#67C23A",
            )
        else:
            self._set_status("❌ 保存失败, 请检查配置文件是否可写。", "#F56C6C")

    def test_connection(self):
        """用表单当前值发起一次最小请求, 验证 API Key / 网络是否可用"""
        if self.ai_thread is not None:
            return  # 上次测试仍在进行 (对象有效且未结束), 忽略连点
        api = self._form_api()
        if not api["api_key"]:
            self._set_status("⚠ 请先填写 API Key 再测试连接。", "#E6A23C")
            return
        self.test_btn.setEnabled(False)
        self._set_status("⏳ 正在测试连接, 请稍候 (约 10~30 秒)…", "#409EFF")
        self.ai_thread = DeepSeekThread(
            api["api_key"],
            "ping",
            base_url=api["base_url"],
            model=api["model"],
            temperature=api["temperature"],
            max_tokens=api["max_tokens"],
            system_prompt="你是一个连接测试助手, 请只回复: 连接成功。",
        )
        self.ai_thread.succeeded.connect(self._on_test_succeeded)
        self.ai_thread.failed.connect(self._on_test_failed)
        self.ai_thread.finished.connect(self._on_ai_thread_finished)
        self.ai_thread.start()

    def restore_defaults(self):
        """恢复出厂默认 AI 参数并保存"""
        defaults = (
            self.cfg.get_factory_defaults()
            .get("power_conversion", {})
            .get("api", {})
        )
        section = self.cfg.config.setdefault("power_conversion", {}).setdefault("api", {})
        section.update({
            "base_url": defaults.get("base_url", DEFAULT_BASE_URL),
            "model": defaults.get("model", DEFAULT_MODEL),
            "api_key": str(defaults.get("api_key", "")),
            "provider": "DeepSeek",
            "temperature": defaults.get("temperature", 0.7),
            "max_tokens": defaults.get("max_tokens", 1500),
        })
        self.cfg.save_config()
        self._load_from_config()
        self._set_status("♻️ 已恢复默认设置并保存 (API Key 已清空)。", "#909399")

    def _toggle_key_visible(self, checked):
        self.key_edit.setEchoMode(
            QLineEdit.EchoMode.Normal if checked else QLineEdit.EchoMode.Password
        )

    def _open_config_folder(self):
        try:
            os.startfile(str(app_root()))
        except OSError as e:
            self._set_status(f"❌ 无法打开文件夹: {e}", "#F56C6C")

    def closeEvent(self, event):
        """窗口关闭: 等待测试/同步线程结束, 避免 QThread destroyed while running"""
        for name in ("ai_thread", "td_thread"):
            thread = getattr(self, name)
            if thread is not None and thread.isRunning():
                thread.requestInterruption()  # 无副作用; 线程有网络超时兜底
                thread.wait(5000)
            if thread is not None and not thread.isRunning():
                setattr(self, name, None)
        super().closeEvent(event)

    def _on_ai_thread_finished(self):
        """线程结束 (成功或失败): 清空引用由 Python GC 回收, 并恢复按钮。
        不再用 deleteLater, 否则 Python 引用指向已删除对象, 再次访问即闪退。"""
        self.ai_thread = None
        self.test_btn.setEnabled(True)

    # ==================== 腾讯文档同步 ====================
    def _td_credentials(self) -> dict:
        """读取腾讯文档凭证: Access Token 直用优先, 否则 Client ID/Secret 换取"""
        access_token = self.td_access_token.text().strip()
        client_id = self.td_client_id.text().strip()
        client_secret = self.td_client_secret.text().strip()
        open_id = self.td_open_id.text().strip()
        if access_token:
            return {
                "access_token": access_token,
                "client_id": client_id,
                "client_secret": client_secret,
                "open_id": open_id,
            }
        if not client_id or not client_secret:
            raise ValueError(
                "请填写 Access Token (应用账号令牌, 直接粘贴 JWT 即可), "
                "或填写 Client ID 与 Client Secret "
                "(腾讯文档开放平台 → 创建应用 → 审核通过后获得)"
            )
        return {
            "access_token": "",
            "client_id": client_id,
            "client_secret": client_secret,
            "open_id": open_id,
        }

    def _start_td_thread(self, operation, payload="", doc_name=""):
        """启动腾讯文档线程 (防连点)"""
        if self.td_thread is not None:
            return False
        try:
            cred = self._td_credentials()
        except ValueError as e:
            self._td_status_msg(f"⚠ {e}", "#E6A23C")
            return False
        client = TencentDocsClient(
            cred["client_id"], cred["client_secret"],
            access_token=cred["access_token"], open_id=cred["open_id"],
        )
        self.td_thread = TencentDocsThread(
            client, operation, payload=payload, doc_name=doc_name
        )
        self.td_thread.succeeded.connect(self._on_td_succeeded)
        self.td_thread.failed.connect(self._on_td_failed)
        self.td_thread.finished.connect(self._on_td_thread_finished)
        self.td_test_btn.setEnabled(False)
        self.td_backup_btn.setEnabled(False)
        self.td_thread.start()
        return True

    def _td_toggle_mode(self, index):
        """凭证方式切换: 0=Access Token, 1=Client ID/Secret, 只显示对应输入区。

        收起用不到的输入区, 让卡片更紧凑。
        """
        self.td_token_box.setVisible(index == 0)
        self.td_cred_box.setVisible(index == 1)

    def _td_test(self):
        """测试腾讯文档连接"""
        if not self._start_td_thread("ping"):
            return
        self._td_status_msg("⏳ 正在测试腾讯文档连接…", "#409EFF")

    def _td_backup(self):
        """一键备份全部配置到腾讯文档"""
        html = build_config_backup_html(
            self.cfg.config, "工作助手配置备份"
        )
        if not self._start_td_thread(
            "backup", payload=html,
            doc_name=f"工作助手配置备份 {self._now_ts()}",
        ):
            return
        self._td_status_msg("⏳ 正在备份到腾讯文档 (上传+导入, 约 10~30 秒)…", "#409EFF")

    @staticmethod
    def _now_ts() -> str:
        from datetime import datetime

        return datetime.now().strftime("%Y-%m-%d %H%M")

    def _on_td_thread_finished(self):
        """腾讯文档线程结束: 清空引用并恢复按钮"""
        self.td_thread = None
        self.td_test_btn.setEnabled(True)
        self.td_backup_btn.setEnabled(True)

    def _on_td_succeeded(self, text):
        """腾讯文档操作成功 (backup 时 text 为在线文档 URL)"""
        if text.startswith("http"):
            self._td_status_msg(
                "✅ 备份成功! 在线文档已生成, 旧版本自动保留:", "#67C23A"
            )
            self.td_last_url.setText(
                f"📄 在线文档: <a href='{text}'>{text}</a>"
            )
            td = self.cfg.config.setdefault("tencent_docs", {})
            td["last_url"] = text
            self.cfg.save_config()
        else:
            hint = ""
            if self.td_access_token.text().strip():
                hint = self._td_token_expire_hint()
            self._td_status_msg(f"✅ {text}" + hint, "#67C23A")

    def _td_token_expire_hint(self) -> str:
        """Access Token 有效期提示 (直用模式)"""
        token = self.td_access_token.text().strip()
        claims = parse_jwt_payload(token)
        exp = claims.get("exp")
        if not isinstance(exp, (int, float)) or exp <= 0:
            return ""
        from datetime import datetime

        try:
            expire = datetime.fromtimestamp(float(exp))
        except (OverflowError, OSError, ValueError):
            return ""
        left_days = int((float(exp) - time.time()) // 86400)
        if left_days < 0:
            return "\n⚠ 该 Access Token 已过期, 请重新获取。"
        return f"\nAccess Token 有效期至 {expire:%Y-%m-%d %H:%M} (约 {left_days} 天后过期)。"

    def _on_td_failed(self, error):
        """腾讯文档操作失败"""
        self._td_status_msg(f"❌ {error}", "#F56C6C")

    def _td_status_msg(self, text, color):
        self.td_status.setText(text)
        self.td_status.setStyleSheet(
            f"color: {color}; background: transparent; border: none;"
        )

    # ==================== 测试结果 ====================
    def _on_test_succeeded(self, text):
        """测试连接成功"""
        self.test_btn.setEnabled(True)
        snippet = text.strip().splitlines()[0][:80] if text.strip() else ""
        self._set_status(f"✅ 连接成功: {snippet}", "#67C23A")

    def _on_test_failed(self, error):
        """测试连接失败: 展示关键错误 (HTTP 401 = Key 无效等)"""
        self.test_btn.setEnabled(True)
        lines = [ln.strip() for ln in str(error).splitlines() if ln.strip()]
        snippet = lines[0][:120] if lines else str(error)[:120]
        self._set_status(f"❌ 连接失败: {snippet}", "#F56C6C")

    # ==================== 工具方法 ====================
    def _set_status(self, text, color="#909399"):
        self.status_label.setText(text)
        self.status_label.setStyleSheet(
            f"color: {color}; background: transparent; border: none;"
        )

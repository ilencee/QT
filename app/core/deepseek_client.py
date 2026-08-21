"""
DeepSeek API 客户端 (共享模块)

被以下页面复用:
- power_conversion_page: 电源设计分析
- text_polish_page:      文本润色

统一从 config.json 的 power_conversion.api 段读取 API 配置。
"""

import json
import urllib.error
import urllib.request

from PyQt6.QtCore import Qt, QThread, pyqtSignal
from PyQt6.QtGui import QFont
from PyQt6.QtWidgets import (
    QDialog, QLabel, QPushButton, QTextBrowser, QVBoxLayout,
)

DEFAULT_SYSTEM_PROMPT = (
    "你是一名资深的电源工程师, 精通 LDO 线性稳压电路设计、"
    "降额使用与散热分析。请用中文给出专业、简洁、可执行的工程建议。"
)
DEFAULT_BASE_URL = "https://api.deepseek.com/chat/completions"
DEFAULT_MODEL = "deepseek-chat"


def load_api_config(cfg):
    """从配置读取 DeepSeek API 参数 (统一读取 power_conversion.api 段)"""
    api_cfg = cfg.config.get("power_conversion", {}).get("api", {})
    return {
        "api_key": str(api_cfg.get("api_key", "")),
        "base_url": str(api_cfg.get("base_url", DEFAULT_BASE_URL)),
        "model": str(api_cfg.get("model", DEFAULT_MODEL)),
        "temperature": float(api_cfg.get("temperature", 0.7)),
        "max_tokens": int(api_cfg.get("max_tokens", 1500)),
    }


class DeepSeekThread(QThread):
    """后台线程调用 DeepSeek API (不阻塞界面)"""
    succeeded = pyqtSignal(str)  # 结果文本
    failed = pyqtSignal(str)     # 错误信息

    def __init__(self, api_key, prompt, base_url, model=DEFAULT_MODEL,
                 temperature=0.7, max_tokens=1500, system_prompt=None, parent=None):
        super().__init__(parent)
        self.api_key = api_key
        self.prompt = prompt
        self.base_url = base_url
        self.model = model
        self.temperature = temperature
        self.max_tokens = max_tokens
        # 可定制 system 提示词; 默认保持电源分析文案 (兼容原页面行为)
        self.system_prompt = system_prompt or DEFAULT_SYSTEM_PROMPT

    def run(self):
        try:
            payload = {
                "model": self.model,
                "messages": [
                    {"role": "system", "content": self.system_prompt},
                    {"role": "user", "content": self.prompt},
                ],
                "temperature": self.temperature,
                "max_tokens": self.max_tokens,
            }
            data = json.dumps(payload).encode("utf-8")
            req = urllib.request.Request(
                self.base_url,
                data=data,
                headers={
                    "Content-Type": "application/json",
                    "Authorization": f"Bearer {self.api_key}",
                },
            )
            with urllib.request.urlopen(req, timeout=60) as resp:
                result = json.loads(resp.read().decode("utf-8"))
            text = result["choices"][0]["message"]["content"]
            self.succeeded.emit(text.strip())
        except urllib.error.HTTPError as e:
            try:
                body = e.read().decode("utf-8", errors="ignore")
            except Exception:
                body = ""
            self.failed.emit(f"HTTP {e.code}: {e.reason}\n{body}")
        except Exception as e:
            self.failed.emit(f"请求失败: {e}")


class DeepSeekDialog(QDialog):
    """DeepSeek 结果独立窗口 (标题/头部文案可定制)"""

    def __init__(self, parent=None, title="🤖 DeepSeek 分析结果",
                 heading="🤖 DeepSeek 分析"):
        super().__init__(parent)
        self.setWindowTitle(title)
        self.resize(720, 560)
        self.setMinimumSize(520, 380)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(12)

        title_label = QLabel(heading)
        title_label.setFont(QFont("Microsoft YaHei", 14, QFont.Weight.Bold))
        layout.addWidget(title_label)

        # QTextBrowser + setMarkdown: AI 返回的 Markdown (标题/列表/代码块等) 直接渲染
        self.text = QTextBrowser()
        self.text.setOpenExternalLinks(True)
        self.text.setStyleSheet("""
            QTextBrowser {
                background: white; border: 1px solid #DCDFE6;
                border-radius: 8px; padding: 12px;
            }
            QTextBrowser a { color: #409EFF; }
        """)
        layout.addWidget(self.text, 1)

        close_btn = QPushButton("关闭")
        close_btn.setMinimumHeight(36)
        close_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        close_btn.setStyleSheet("""
            QPushButton {
                background: #409EFF; color: white; border: none;
                border-radius: 6px; padding: 6px 12px; font-weight: bold;
            }
            QPushButton:hover { background: #66B1FF; }
            QPushButton:pressed { background: #337ECC; }
        """)
        close_btn.clicked.connect(self.accept)
        layout.addWidget(close_btn)

    def set_message(self, text):
        """显示纯文本 (用于加载中/错误提示)"""
        self.text.setPlainText(text)

    def set_markdown(self, text):
        """渲染 Markdown 文本 (用于 AI 分析结果)"""
        self.text.setMarkdown(text)

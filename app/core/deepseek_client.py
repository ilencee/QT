"""
DeepSeek API 客户端 (共享模块)

被以下页面复用:
- power_conversion_page: 电源设计分析
- text_polish_page:      文本润色

统一从 config.json 的 power_conversion.api 段读取 API 配置。
"""

import html as _html
import json
import re
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
    """从配置读取 DeepSeek API 参数 (统一读取 power_conversion.api 段)

    对 config.json 中的非法数值做防御式解析: 类型/范围错误时回退默认值,
    避免手改配置 (如 temperature 写成字符串) 导致页面崩溃。
    """
    api_cfg = cfg.config.get("power_conversion", {}).get("api", {})
    try:
        temperature = float(api_cfg.get("temperature", 0.7))
    except (TypeError, ValueError):
        temperature = 0.7
    temperature = min(2.0, max(0.0, temperature))  # DeepSeek 合法范围 [0, 2]
    try:
        max_tokens = int(api_cfg.get("max_tokens", 1500))
    except (TypeError, ValueError):
        max_tokens = 1500
    max_tokens = min(8192, max(1, max_tokens))
    return {
        "api_key": str(api_cfg.get("api_key", "")),
        "base_url": str(api_cfg.get("base_url", DEFAULT_BASE_URL)),
        "model": str(api_cfg.get("model", DEFAULT_MODEL)),
        "temperature": temperature,
        "max_tokens": max_tokens,
    }


def md_to_html(text):
    """轻量 Markdown → HTML (补足 Qt setMarkdown 的短板)

    QTextBrowser.setMarkdown 不支持 GFM 表格, 且会把段落内单个换行折叠成
    空格, 导致 AI 输出的表格/逐行内容挤成一段。此函数在保留常用语法
    (标题/列表/代码块/引用/粗体/斜体/链接/图片/删除线) 的同时, 额外支持
    表格渲染与段内换行 (<br>), 供 QTextBrowser.setHtml 使用。
    """
    text = (text or "").replace("\r\n", "\n").replace("\r", "\n")
    lines = text.split("\n")

    def _inline(s):
        s = _html.escape(s, quote=False)
        s = re.sub(r"!\[([^\]]*)\]\(([^)\s]+)\)", r'<img src="\2" alt="\1" />', s)
        s = re.sub(r"\[([^\]]+)\]\(([^)\s]+)\)", r'<a href="\2">\1</a>', s)
        s = re.sub(r"`([^`]+)`", r"<code>\1</code>", s)
        s = re.sub(r"\*\*([^*\n]+)\*\*", r"<b>\1</b>", s)
        s = re.sub(r"__([^_\n]+)__", r"<b>\1</b>", s)
        s = re.sub(r"(?<!\*)\*([^*\n]+)\*(?!\*)", r"<i>\1</i>", s)
        s = re.sub(r"(?<!_)_([^_\n]+)_(?!_)", r"<i>\1</i>", s)
        s = re.sub(r"~~([^~\n]+)~~", r"<s>\1</s>", s)
        return s

    def _render_table(rows):
        parts = [
            '<table border="1" cellspacing="0" cellpadding="4"'
            ' style="border-collapse: collapse; margin: 6px 0;">'
        ]
        for idx, row in enumerate(rows):
            cells = [c.strip() for c in row.strip().strip("|").split("|")]
            tag = "th" if idx == 0 else "td"
            inner = "".join(f"<{tag}>{_inline(c)}</{tag}>" for c in cells)
            parts.append(f"<tr>{inner}</tr>")
        parts.append("</table>")
        return "\n".join(parts)

    out = []
    para = []
    in_code = False
    code = []
    ul_open = 0
    ol_open = 0
    quote = []

    def flush_para():
        nonlocal para
        if para:
            body = "<br>".join(_inline(x) for x in para)
            out.append(f"<p>{body}</p>")
            para = []

    def close_ol():
        nonlocal ol_open
        if ol_open:
            out.append("</ol>")
            ol_open = 0

    def close_ul():
        nonlocal ul_open
        if ul_open:
            out.append("</ul>")
            ul_open = 0

    def flush_quote():
        nonlocal quote
        if quote:
            body = "<br>".join(_inline(x) for x in quote)
            out.append(f"<blockquote>{body}</blockquote>")
            quote = []

    def flush_blocks():
        flush_para()
        close_ol()
        close_ul()
        flush_quote()

    n = len(lines)
    i = 0
    while i < n:
        line = lines[i]
        stripped = line.strip()

        if stripped.startswith("```"):
            if in_code:
                out.append("<pre><code>" + _html.escape("\n".join(code)) + "</code></pre>")
                code = []
                in_code = False
            else:
                flush_blocks()
                in_code = True
            i += 1
            continue
        if in_code:
            code.append(line)
            i += 1
            continue

        if not stripped:
            flush_blocks()
            i += 1
            continue

        # 标题
        m = re.match(r"^(#{1,6})\s+(.*)$", line)
        if m:
            flush_blocks()
            level = len(m.group(1))
            out.append(f"<h{level}>{_inline(m.group(2))}</h{level}>")
            i += 1
            continue

        # GFM 表格: 连续以 | 开头的行
        if line.lstrip().startswith("|") and line.count("|") >= 2:
            flush_blocks()
            rows = [line]
            j = i + 1
            while j < n and lines[j].lstrip().startswith("|") and lines[j].count("|") >= 2:
                rows.append(lines[j])
                j += 1
            # 跳过分隔行 | --- | :---: |
            if len(rows) >= 2 and re.match(r"^\s*\|?[\s:\-|]+\|?\s*$", rows[1]) and "-" in rows[1]:
                rows = [rows[0]] + rows[2:]
            out.append(_render_table(rows))
            i = j
            continue

        # 引用
        if stripped.startswith(">"):
            flush_para()
            close_ol()
            close_ul()
            quote.append(stripped.lstrip(">").strip())
            i += 1
            continue

        # 无序列表
        m = re.match(r"^\s*[-*+]\s+(.*)$", line)
        if m:
            flush_para()
            flush_quote()
            close_ol()
            if not ul_open:
                out.append("<ul>")
                ul_open = 1
            out.append(f"<li>{_inline(m.group(1))}</li>")
            i += 1
            continue

        # 有序列表
        m = re.match(r"^\s*\d+[.)]\s+(.*)$", line)
        if m:
            flush_para()
            flush_quote()
            close_ul()
            if not ol_open:
                out.append("<ol>")
                ol_open = 1
            out.append(f"<li>{_inline(m.group(1))}</li>")
            i += 1
            continue

        # 水平线
        if re.match(r"^\s*([-*_])\s*(\1\s*){2,}$", line):
            flush_blocks()
            out.append("<hr>")
            i += 1
            continue

        # 普通段落行 (段内换行保留为 <br>, 避免挤成一段)
        if not para:
            close_ol()
            close_ul()
            flush_quote()
        para.append(line)
        i += 1

    if in_code:
        out.append("<pre><code>" + _html.escape("\n".join(code)) + "</code></pre>")
    flush_blocks()
    return "\n".join(out)


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
            # 防御 API 返回非预期结构 (HTTP 200 但无 choices / 内容为空)
            choices = result.get("choices") or []
            if not choices:
                err = result.get("error", {}).get("message", "API 未返回结果 (choices 为空)")
                self.failed.emit(f"请求失败: {err}")
                return
            text = choices[0].get("message", {}).get("content", "")
            if not text:
                self.failed.emit("请求失败: API 返回内容为空")
                return
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
        """渲染 Markdown 文本 (用于 AI 分析结果)

        经 md_to_html 转换: 支持 GFM 表格, 且段落内单换行保留为 <br>,
        避免内容挤成一段。
        """
        self.text.setHtml(md_to_html(text))

# -*- coding: utf-8 -*-
"""
腾讯文档同步 (备份到腾讯文档, 防止配置/模板丢失)

基于腾讯文档开放平台 OpenAPI 实现:
- 鉴权: 应用账号 token, GET https://docs.qq.com/oauth/v2/app-account-token
  (只需 Client ID + Client Secret, 无需用户扫码, 适合桌面工具)
- 备份: 本地 HTML 文件 → 预导入 → 上传 COS → 异步导入 → 轮询进度 → 在线文档 URL
- 说明: OpenAPI 无"更新已有文档"接口, 每次备份生成新文档 (文件名带时间戳),
  天然形成版本历史, 旧版本保留在腾讯文档中, 可从其中任一版本恢复

前置条件: 需在腾讯文档开放合作平台注册开发者并创建应用 (审核通过后获得
Client ID / Client Secret), 参考 https://docs.qq.com/open/document/app/

接口参考: https://docs.qq.com/open/document/app/ (官方开放平台开发文档)
         https://github.com/easy-wx/qq-doc (社区 Python 封装, 接口与官方一致)
"""
import base64
import hashlib
import html as html_mod
import io
import json
import re
import tempfile
import time
import zipfile
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime
from pathlib import Path

from PyQt6.QtCore import QThread, pyqtSignal

BASE_URL = "https://docs.qq.com"
OAUTH_TOKEN_URL = BASE_URL + "/oauth/v2/app-account-token"
API_URL = BASE_URL + "/openapi/drive/v2"

MIME_BY_EXT = {
    "html": "text/html",
    "htm": "text/html",
    "txt": "text/plain",
    "md": "text/markdown",
    "doc": "application/msword",
    "docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    "xls": "application/vnd.ms-excel",
    "xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    "csv": "text/csv",
    "pdf": "application/pdf",
}


class TencentDocsError(Exception):
    """腾讯文档 OpenAPI 调用失败"""


def _now_str() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def parse_jwt_payload(token: str) -> dict:
    """解析 JWT 的 payload 段 (base64url → dict)。

    不校验签名, 仅读取声明字段。用于直用 Access Token 模式时提取
    client_id (clt) / open_id (sub) / 过期时间 (exp) 等。
    """
    token = (token or "").strip()
    parts = token.split(".")
    if len(parts) != 3:
        return {}
    try:
        payload = parts[1]
        payload += "=" * (-len(payload) % 4)
        data = json.loads(base64.urlsafe_b64decode(payload.encode("ascii")))
        return data if isinstance(data, dict) else {}
    except Exception:  # noqa: BLE001 - 任何解析失败都视为无效 token
        return {}


def build_backup_html(doc_title: str, sections) -> str:
    """把 [(标题, 内容), ...] 组装为可导入腾讯文档的 HTML 备份文档。

    sections 元素可为二元组 (标题, 文本) 或三元组 (标题, 文本, raw)。
    raw=True 时内容不转义直接嵌入 (用于本身是 HTML 的模板, 保留图片 data URI)。
    """
    parts = [
        "<!DOCTYPE html><html><head><meta charset='utf-8'>"
        f"<title>{html_mod.escape(doc_title)}</title></head><body>",
        f"<h1>{html_mod.escape(doc_title)}</h1>",
        f"<p style='color:#666'>生成时间: {_now_str()}</p>",
        "<hr>",
    ]
    for section in sections:
        raw = len(section) >= 3 and bool(section[2])
        title, text = section[0], section[1]
        parts.append(f"<h2>{html_mod.escape(str(title))}</h2>")
        if raw:
            parts.append(f"<div class='raw'>{text}</div>")
        else:
            parts.append(f"<pre>{html_mod.escape(str(text))}</pre>")
    parts.append("</body></html>")
    return "".join(parts)


def build_config_backup_html(config: dict, doc_title: str) -> str:
    """把完整 config 组装为备份 HTML: 可读章节 + 文末完整 JSON (恢复用)"""
    sections = []
    burn = (
        config.get("text_polish", {})
        .get("types", {})
        .get("烧录指导", {})
    )
    chips = burn.get("chips", {}) if isinstance(burn, dict) else {}
    constraints = burn.get("constraints", []) if isinstance(burn, dict) else []
    if isinstance(constraints, str):
        constraints = [constraints]

    chip_sections = []
    chips_has_img = False
    for chip, cfg in chips.items():
        if not isinstance(cfg, dict):
            continue
        role = str(cfg.get("system_role", "") or "").strip()
        template = str(cfg.get("template", "") or "").strip()
        if "<img" in template.lower() or "data:image/" in template.lower():
            chips_has_img = True
        chip_sections.append((chip, role, template))
    if chip_sections:
        # 模板本身是 HTML (可能含插图), 用 raw 模式原样嵌入, 保留图片
        if chips_has_img:
            lines = []
            for chip, role, template in chip_sections:
                lines.append(f"<b>◆ {html_mod.escape(chip)}</b>")
                if role:
                    lines.append(f"<p>角色设定: {html_mod.escape(role)}</p>")
                lines.append(f"<div>模板内容:<br>{template}</div>")
            sections.append(("烧录指导芯片模板", "<br>".join(lines), True))
        else:
            lines = []
            for chip, role, template in chip_sections:
                lines.append(f"◆ {chip}")
                if role:
                    lines.append(f"  角色设定: {role}")
                lines.append(f"  模板内容:\n{template}\n")
            sections.append(("烧录指导芯片模板", "\n".join(lines)))

        c_lines = [f"{i+1}. {c}" for i, c in enumerate(constraints)]
        sections.append(("烧录指导通用限制条件", "\n".join(c_lines)))

    other_types = {
        k: v
        for k, v in (config.get("text_polish", {}).get("types", {}) or {}).items()
        if k != "烧录指导" and isinstance(v, dict)
    }
    other_has_img = any(
        "<img" in str(cfg.get("template", "") or "").lower()
        or "data:image/" in str(cfg.get("template", "") or "").lower()
        for cfg in other_types.values()
    )
    if other_types:
        if other_has_img:
            lines = []
            for name, cfg in other_types.items():
                role = str(cfg.get("system_role", "") or "").strip()
                template = str(cfg.get("template", "") or "").strip()
                cons = cfg.get("constraints", [])
                if isinstance(cons, str):
                    cons = [cons]
                lines.append(f"<b>◆ {html_mod.escape(name)}</b>")
                if role:
                    lines.append(f"<p>角色设定: {html_mod.escape(role)}</p>")
                lines.append(f"<div>模板内容:<br>{template}</div>")
                if cons:
                    c_html = "<br>".join(f"{i+1}. {html_mod.escape(str(c))}" for i, c in enumerate(cons))
                    lines.append(f"<p>限制条件:<br>{c_html}</p>")
            sections.append(("其他文档类型配置", "<br>".join(lines), True))
        else:
            lines = []
            for name, cfg in other_types.items():
                role = str(cfg.get("system_role", "") or "").strip()
                template = str(cfg.get("template", "") or "").strip()
                cons = cfg.get("constraints", [])
                if isinstance(cons, str):
                    cons = [cons]
                lines.append(f"◆ {name}")
                if role:
                    lines.append(f"  角色设定: {role}")
                lines.append(f"  模板内容:\n{template}")
                if cons:
                    lines.append("  限制条件:")
                    lines += [f"    {i+1}. {c}" for i, c in enumerate(cons)]
                lines.append("")
            sections.append(("其他文档类型配置", "\n".join(lines)))

    api = (config.get("power_conversion", {}) or {}).get("api", {}) or {}
    if api:
        lines = [
            f"服务商: {api.get('provider', '')}",
            f"Base URL: {api.get('base_url', '')}",
            f"模型: {api.get('model', '')}",
            f"Temperature: {api.get('temperature', '')}",
            f"Max Tokens: {api.get('max_tokens', '')}",
            "API Key: 已包含在文末完整 JSON 中 (敏感信息, 注意保管文档链接权限)",
        ]
        sections.append(("AI 服务配置", "\n".join(lines)))

    sections.append(
        ("完整配置 JSON (恢复时直接使用)", json.dumps(config, ensure_ascii=False, indent=2))
    )
    return build_backup_html(doc_title, sections)


# ---------------------------------------------------------------- docx 生成
_IMG_DATA_RE = re.compile(
    r"""<img[^>]*\bsrc=["']data:image/(?P<mime>png|jpeg|gif|webp|x-icon);base64,(?P<b64>[A-Za-z0-9+/=]+)["'][^>]*>""",
    re.IGNORECASE,
)
_IMG_EXT = {
    "png": ".png",
    "jpeg": ".jpg",
    "gif": ".gif",
    "webp": ".webp",
    "x-icon": ".png",
}
_IMG_CTYPE = {
    "png": "image/png",
    "jpeg": "image/jpeg",
    "gif": "image/gif",
    "webp": "image/webp",
    "x-icon": "image/png",
}


def _png_size(data: bytes):
    if data[:8] != b"\x89PNG\r\n\x1a\n" or len(data) < 24:
        return None
    w, h = data[16:20], data[20:24]
    return (int.from_bytes(w, "big"), int.from_bytes(h, "big"))


def _jpeg_size(data: bytes):
    if data[:2] != b"\xff\xd8":
        return None
    i = 2
    while i + 9 < len(data):
        if data[i] != 0xFF:
            i += 1
            continue
        marker = data[i + 1]
        if marker in (0xD8, 0x01) or 0xD0 <= marker <= 0xD7:
            i += 2
            continue
        seg_len = int.from_bytes(data[i + 2:i + 4], "big")
        if seg_len < 2:
            return None
        if 0xC0 <= marker <= 0xC3 or 0xC5 <= marker <= 0xC7 or \
           0xC9 <= marker <= 0xCB or 0xCD <= marker <= 0xCF:
            return (int.from_bytes(data[i + 7:i + 9], "big"),
                    int.from_bytes(data[i + 5:i + 7], "big"))
        i += 2 + seg_len
    return None


def _image_emu(data: bytes, mime: str):
    """返回 (宽EMU, 高EMU), 默认 400x300 px 缩放"""
    size = _png_size(data) if mime == "png" else (_jpeg_size(data) if mime == "jpeg" else None)
    w_px, h_px = (size if size and size[0] > 0 and size[1] > 0 else (400, 300))
    max_w = 500  # 文档内最大显示宽度 px
    if w_px > max_w:
        h_px = int(h_px * max_w / w_px)
        w_px = max_w
    return w_px * 9525, h_px * 9525  # 1px ≈ 9525 EMU


def build_docx_from_html(html_text: str) -> bytes:
    """把 HTML (含 data URI 图片) 转成最小合法 .docx 文件内容。

    腾讯文档导入接口不支持 .html, 但支持 .docx, 因此备份前先把
    build_config_backup_html 生成的 HTML 转成 docx, 图片以内嵌方式保留。
    """
    images = []          # [(mime, bytes)]
    text_parts = []      # [("text", str) | ("img", idx)]

    def _img_repl(m):
        try:
            raw = base64.b64decode(m.group("b64"))
        except Exception:  # noqa: BLE001
            return ""
        mime = m.group("mime").lower()
        images.append((mime, raw))
        return f"\x00IMG{len(images) - 1}\x00"

    body = _IMG_DATA_RE.sub(_img_repl, html_text)
    # 块级标签 → 换行, 其余标签剥除
    body = re.sub(r"</(p|div|h[1-6]|li|tr|pre|section|article)>", "\n", body, flags=re.IGNORECASE)
    body = re.sub(r"<br\s*/?>", "\n", body, flags=re.IGNORECASE)
    body = re.sub(r"<[^>]+>", "", body)
    body = html_mod.unescape(body)

    for line in body.split("\n"):
        line = line.strip()
        if not line:
            continue
        for seg in re.split(r"\x00(IMG\d+)\x00", line):
            if not seg:
                continue
            m = re.fullmatch(r"IMG(\d+)", seg)
            if m:
                text_parts.append(("img", int(m.group(1))))
            else:
                text_parts.append(("text", seg))

    def _xml_escape(s: str) -> str:
        return s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")

    # document.xml
    body_xml = []
    img_id = 0
    for kind, val in text_parts:
        if kind == "text":
            body_xml.append(
                f'<w:p><w:r><w:t xml:space="preserve">{_xml_escape(val)}</w:t></w:r></w:p>'
            )
        else:
            mime, data = images[val]
            w_emu, h_emu = _image_emu(data, mime)
            img_id += 1
            rid = f"rIdImg{img_id}"
            body_xml.append(
                '<w:p><w:r><w:drawing>'
                f'<wp:inline distT="0" distB="0" distL="0" distR="0">'
                f'<wp:extent cx="{w_emu}" cy="{h_emu}"/>'
                f'<wp:effectExtent l="0" t="0" r="0" b="0"/>'
                f'<wp:docPr id="{img_id}" name="图片{img_id}"/>'
                '<a:graphic xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main">'
                '<a:graphicData uri="http://schemas.openxmlformats.org/drawingml/2006/picture">'
                '<pic:pic xmlns:pic="http://schemas.openxmlformats.org/drawingml/2006/picture">'
                f'<pic:nvPicPr><pic:cNvPr id="{img_id}" name="图片{img_id}"/><pic:cNvPicPr/></pic:nvPicPr>'
                f'<pic:blipFill><a:blip r:embed="{rid}"/><a:stretch><a:fillRect/></a:stretch></pic:blipFill>'
                '<pic:spPr><a:xfrm><a:off x="0" y="0"/>'
                f'<a:ext cx="{w_emu}" cy="{h_emu}"/></a:xfrm>'
                '<a:prstGeom prst="rect"><a:avLst/></a:prstGeom></pic:spPr>'
                '</pic:pic></a:graphicData></a:graphic>'
                '</wp:inline></w:drawing></w:r></w:p>'
            )

    document_xml = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main" '
        'xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships" '
        'xmlns:wp="http://schemas.openxmlformats.org/drawingml/2006/wordprocessingDrawing" '
        'xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main" '
        'xmlns:pic="http://schemas.openxmlformats.org/drawingml/2006/picture">'
        "<w:body>" + "".join(body_xml) +
        '<w:sectPr><w:pgSz w:w="11906" w:h="16838"/>'
        '<w:pgMar w:top="1440" w:right="1440" w:bottom="1440" w:left="1440"/></w:sectPr>'
        "</w:body></w:document>"
    )

    # rels: 图片关系
    doc_rels = []
    for i in range(1, img_id + 1):
        mime = images[i - 1][0] if i - 1 < len(images) else "png"
        doc_rels.append(
            f'<Relationship Id="rIdImg{i}" '
            'Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/image" '
            f'Target="media/image{i}{_IMG_EXT.get(mime, ".png")}"/>'
        )
    document_rels_xml = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
        + "".join(doc_rels) + "</Relationships>"
    )

    content_types_defaults = []
    for mime in sorted(set(m for m, _ in images)):
        content_types_defaults.append(
            f'<Default Extension="{_IMG_EXT.get(mime, "png").lstrip(".")}" ContentType="{_IMG_CTYPE.get(mime, "image/png")}"/>'
        )
    content_types_xml = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
        '<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>'
        '<Default Extension="xml" ContentType="application/xml"/>'
        + "".join(content_types_defaults) +
        '<Override PartName="/word/document.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"/>'
        "</Types>"
    )

    rels_xml = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
        '<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" '
        'Target="word/document.xml"/></Relationships>'
    )

    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("[Content_Types].xml", content_types_xml)
        zf.writestr("_rels/.rels", rels_xml)
        zf.writestr("word/document.xml", document_xml)
        zf.writestr("word/_rels/document.xml.rels", document_rels_xml)
        for i, (mime, data) in enumerate(images):
            zf.writestr(f"word/media/image{i + 1}{_IMG_EXT.get(mime, '.png')}", data)
    return buf.getvalue()


class TencentDocsClient:
    """腾讯文档 OpenAPI 客户端 (应用账号模式)

    access_token 直用模式: 传入已申请到的应用账号 Access Token (JWT) 时,
    跳过 Client ID/Secret 换取流程, 直接用该 token 调用 OpenAPI。
    (token 一般有效期 30 天, 过期后在设置页重新获取/粘贴即可)
    """

    def __init__(self, client_id: str = "", client_secret: str = "",
                 access_token: str = "", open_id: str = "", timeout: int = 60):
        self.client_id = client_id.strip()
        self.client_secret = client_secret.strip()
        self.timeout = timeout
        self._access_token = access_token.strip()
        self._open_id = ""
        self._token_expire_at = 0.0
        # 直用模式下从 JWT payload 提取 open_id 与过期时间
        if self._access_token:
            claims = parse_jwt_payload(self._access_token)
            exp = claims.get("exp")
            if isinstance(exp, (int, float)) and exp > 0:
                self._token_expire_at = float(exp)
            if not self.client_id:
                self.client_id = str(claims.get("clt", "") or "").strip()
            if not open_id:
                open_id = str(claims.get("sub", "") or "").strip()
        # 显式传入的 open_id 优先级最高 (直用 JWT 无 sub 或普通模式换取响应缺失时手动补填)
        self._open_id = open_id.strip()

    @property
    def token_expire_hint(self) -> str:
        """Access Token 有效期提示 (直用模式)"""
        if not self._access_token or self._token_expire_at <= 0:
            return ""
        from datetime import datetime as _dt

        try:
            expire = _dt.fromtimestamp(self._token_expire_at)
        except (OverflowError, OSError, ValueError):
            return ""
        left = int(self._token_expire_at - time.time())
        if left <= 0:
            return f"⚠ 该 Access Token 已过期 ({expire:%Y-%m-%d %H:%M}), 请重新获取。"
        return f"Access Token 有效期至 {expire:%Y-%m-%d %H:%M} ({left//86400} 天后过期)。"

    # ==================== 基础请求 ====================
    def _http_json(self, method, url, params=None, data=None, headers=None, timeout=None):
        if params:
            url = url + "?" + urllib.parse.urlencode(params)
        req = urllib.request.Request(url, method=method, data=data)
        for k, v in (headers or {}).items():
            req.add_header(k, v)
        try:
            with urllib.request.urlopen(
                req, timeout=timeout or self.timeout
            ) as resp:
                body = resp.read().decode("utf-8", "replace")
                status = resp.status
        except urllib.error.HTTPError as e:
            try:
                body = e.read().decode("utf-8", "replace")
            except Exception:
                body = ""
            status = e.code
        except urllib.error.URLError as e:
            raise TencentDocsError(f"网络错误: {e.reason}") from e
        if status >= 400:
            snippet = body[:300].strip()
            raise TencentDocsError(f"HTTP {status}: {snippet or '请求失败'}")
        if not body:
            return {}
        try:
            return json.loads(body)
        except json.JSONDecodeError:
            return {}

    def _get_access_token(self):
        """获取/刷新应用账号 token

        - 直用模式 (__init__ 传入了 access_token): 直接用, 不发起换取请求
        - 普通模式: 用 Client ID/Secret 换取, 内存缓存, 过期重取
        """
        if self._access_token:
            if self._token_expire_at and time.time() >= self._token_expire_at:
                raise TencentDocsError(
                    "Access Token 已过期, 请到 系统设置 → 腾讯文档同步 中重新获取/粘贴。"
                )
            return  # 直用模式: 直接用已配置的 token
        if not self.client_id or not self.client_secret:
            raise TencentDocsError(
                "未配置 Client ID / Client Secret, 请先在系统设置 → 腾讯文档同步中填写"
            )
        resp = self._http_json(
            "GET",
            OAUTH_TOKEN_URL,
            params={
                "client_id": self.client_id,
                "client_secret": self.client_secret,
            },
        )
        token = resp.get("access_token") or resp.get("data", {}).get("access_token", "")
        if not token:
            raise TencentDocsError(
                f"获取腾讯文档访问令牌失败: {json.dumps(resp, ensure_ascii=False)[:200]}"
                " (请确认应用已审核通过、Client ID/Secret 正确, 且已配置相应权限)"
            )
        self._access_token = token
        if not self._open_id:  # 显式传入的 open_id 优先, 换取响应仅作补充
            self._open_id = str(
                resp.get("user_id")
                or resp.get("open_id")
                or resp.get("data", {}).get("user_id", "")
                or ""
            )
        expires_in = int(
            resp.get("expires_in")
            or resp.get("data", {}).get("expires_in", 0)
            or 3600
        )
        self._token_expire_at = time.time() + max(expires_in, 60) - 30

    def _headers(self) -> dict:
        self._get_access_token()
        headers = {
            "Access-Token": self._access_token,
            "Client-Id": self.client_id,
            "Accept": "application/json",
        }
        if self._open_id:
            headers["Open-Id"] = self._open_id
        return headers

    # ==================== 连接测试 ====================
    def ping(self):
        """验证 Client ID / Secret 是否可用 (拉取根目录列表)"""
        self._get_access_token()
        resp = self._http_json(
            "GET", API_URL + "/folders", headers=self._headers()
        )
        return resp

    # ==================== 文件夹 ====================
    def create_folder(self, title: str, parent: str = "") -> dict:
        body = urllib.parse.urlencode({"title": title}).encode("utf-8")
        params = {}
        if parent:
            params["parentfolderID"] = parent
        headers = self._headers()
        headers["Content-Type"] = "application/x-www-form-urlencoded"
        resp = self._http_json(
            "POST", API_URL + "/folders", params=params, data=body, headers=headers
        )
        return resp.get("data", resp)

    def list_folder_contents(self, folder_id: str = "") -> list:
        url = API_URL + "/folders" + (f"/{folder_id}" if folder_id else "")
        resp = self._http_json("GET", url, headers=self._headers())
        data = resp.get("data", resp)
        if isinstance(data, dict):
            return data.get("list", []) or []
        return []

    # ==================== 上传导入 ====================
    @staticmethod
    def _file_md5(path: str) -> str:
        h = hashlib.md5()
        with open(path, "rb") as f:
            for chunk in iter(lambda: f.read(1 << 20), b""):
                h.update(chunk)
        return h.hexdigest()

    def _create_import_info(self, file_md5: str, file_name: str, file_size: int) -> dict:
        body = urllib.parse.urlencode({
            "fileMD5": file_md5,
            "fileName": file_name,
            "fileSize": file_size,
        }).encode("utf-8")
        headers = self._headers()
        headers["Content-Type"] = "application/x-www-form-urlencoded"
        resp = self._http_json(
            "POST", API_URL + "/files/upload-url", data=body, headers=headers
        )
        data = resp.get("data", resp)
        if not data:
            raise TencentDocsError(f"预导入失败: {json.dumps(resp, ensure_ascii=False)[:200]}")
        return data

    def _upload_to_cos(self, cos_put_url: str, path: str, mime: str):
        with open(path, "rb") as f:
            payload = f.read()
        req = urllib.request.Request(
            cos_put_url, method="PUT", data=payload
        )
        req.add_header("Content-Type", mime)
        try:
            with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                if resp.status >= 400:
                    raise TencentDocsError(f"COS 上传失败: HTTP {resp.status}")
        except urllib.error.HTTPError as e:
            raise TencentDocsError(f"COS 上传失败: HTTP {e.code}") from e
        except urllib.error.URLError as e:
            raise TencentDocsError(f"COS 上传失败: {e.reason}") from e

    def _async_import(self, file_md5: str, file_name: str, cos_file_key: str, parent_folder_id: str) -> str:
        params = {"fileMD5": file_md5, "fileName": file_name, "COSFileKey": cos_file_key}
        if parent_folder_id:
            params["parentfolderID"] = parent_folder_id
        headers = self._headers()
        headers["Content-Type"] = "application/x-www-form-urlencoded"
        resp = self._http_json(
            "POST", API_URL + "/files/async-import",
            data=urllib.parse.urlencode(params).encode("utf-8"),
            headers=headers,
        )
        data = resp.get("data", resp)
        progress_id = (
            data.get("progressQueryID")
            or data.get("progressQueryId")
            or data.get("taskId")
            or ""
        )
        if not progress_id:
            raise TencentDocsError(f"异步导入失败: {json.dumps(resp, ensure_ascii=False)[:200]}")
        return str(progress_id)

    def _poll_import_progress(self, progress_query_id: str, timeout: float = 180.0) -> dict:
        start = time.time()
        while time.time() - start < timeout:
            resp = self._http_json(
                "GET", API_URL + "/files/import-progress",
                params={"progressQueryID": progress_query_id},
                headers=self._headers(),
            )
            data = resp.get("data", resp)
            if isinstance(data, dict) and data.get("ID"):
                return data
            time.sleep(1)
        raise TencentDocsError("导入腾讯文档超时, 请稍后到腾讯文档中查看是否已生成")

    def upload_file(self, path: str, file_name: str = "", parent_folder_id: str = "",
                    poll_timeout: float = 180.0) -> dict:
        """上传本地文件并导入为腾讯在线文档, 返回 data (含 ID / url 等)"""
        file_name = file_name or Path(path).name
        md5 = self._file_md5(path)
        size = Path(path).stat().st_size
        info = self._create_import_info(md5, file_name, size)
        cos_url = info.get("COSPutURL") or info.get("cosPutUrl") or ""
        cos_key = info.get("COSFileKey") or info.get("cosFileKey") or ""
        if not cos_url or not cos_key:
            raise TencentDocsError("预导入接口未返回上传地址, 无法继续")
        mime = MIME_BY_EXT.get(Path(path).suffix.lower().lstrip("."), "application/octet-stream")
        self._upload_to_cos(cos_url, path, mime)
        progress_id = self._async_import(md5, file_name, cos_key, parent_folder_id)
        return self._poll_import_progress(progress_id, poll_timeout)

    def upload_html(self, html: str, doc_name: str = "", parent_folder_id: str = "",
                    poll_timeout: float = 180.0) -> str:
        """把 HTML 内容备份为腾讯在线文档, 返回在线文档 URL。

        腾讯文档导入接口不支持 .html, 因此先把 HTML 转成 .docx 再上传,
        图片 (data URI) 以内嵌方式保留。
        """
        docx_bytes = build_docx_from_html(html)
        file_name = doc_name or f"备份_{_now_str().replace(':', '-')}.docx"
        if not Path(file_name).suffix:
            file_name += ".docx"
        with tempfile.NamedTemporaryFile("wb", suffix=".docx", delete=False) as f:
            f.write(docx_bytes)
            tmp = f.name
        try:
            data = self.upload_file(tmp, file_name=file_name, parent_folder_id=parent_folder_id,
                                    poll_timeout=poll_timeout)
            return doc_url(data)
        finally:
            try:
                Path(tmp).unlink(missing_ok=True)
            except OSError:
                pass


def doc_url(data: dict) -> str:
    """从导入结果 data 中提取在线文档 URL"""
    url = data.get("url") or data.get("URL") or ""
    if url:
        return str(url)
    file_id = data.get("ID") or data.get("file_id") or data.get("fileId") or ""
    if file_id:
        return f"{BASE_URL}/doc/{file_id}"
    return f"{BASE_URL}/doc/{str(data.get('id', ''))}"


class TencentDocsThread(QThread):
    """腾讯文档同步线程 (避免阻塞 UI)

    用法: 传入 client 与 operation, 通过 succeeded / failed / finished 信号取结果;
    不要 deleteLater, finished 槽中置 None 由 GC 回收 (与项目其他线程一致)。
    """
    succeeded = pyqtSignal(str)
    failed = pyqtSignal(str)
    finished = pyqtSignal()

    def __init__(self, client: TencentDocsClient, operation: str, payload: str = "",
                 doc_name: str = "", parent_folder_id: str = "", parent=None):
        super().__init__(parent)
        self.client = client
        self.operation = operation
        self.payload = payload
        self.doc_name = doc_name
        self.parent_folder_id = parent_folder_id

    def run(self):
        try:
            if self.operation == "ping":
                self.client.ping()
                self.succeeded.emit("✅ 连接成功: 腾讯文档 OpenAPI 可用")
            elif self.operation == "backup":
                url = self.client.upload_html(
                    self.payload, doc_name=self.doc_name,
                    parent_folder_id=self.parent_folder_id,
                )
                self.succeeded.emit(url)
            else:
                self.failed.emit(f"未知操作: {self.operation}")
        except Exception as e:  # noqa: BLE001 - 统一转字符串给 UI
            self.failed.emit(str(e))
        finally:
            self.finished.emit()

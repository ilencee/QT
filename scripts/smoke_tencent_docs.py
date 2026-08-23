# -*- coding: utf-8 -*-
"""冒烟测试: 腾讯文档同步 (客户端全流程 mock / 备份文档构建 / 设置页与润色页入口)"""
import json
import os
import sys
from unittest import mock

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from PyQt6.QtWidgets import QApplication

from app.core.tencent_docs import (
    TencentDocsClient,
    build_backup_html,
    build_config_backup_html,
    build_docx_from_html,
    doc_url,
    parse_jwt_payload,
)

app = QApplication(sys.argv)

# 1. 备份 HTML 构建 (真实 config)
cfg = json.load(open("config.json", encoding="utf-8"))
html = build_config_backup_html(cfg, "测试备份")
assert "<h1>测试备份</h1>" in html, "缺标题"
assert "烧录指导芯片模板" in html, "缺烧录指导章节"
assert "完整配置 JSON" in html, "缺完整 JSON 章节"
assert html.rstrip().endswith("</html>"), "HTML 未闭合"

# 转义: <pre> 内容不应把脚本当标签
html2 = build_backup_html("T", [("h", "<b>x</b> & <script>")])
assert "&lt;b&gt;x&lt;/b&gt;" in html2 and "&lt;script&gt;" in html2, "HTML 未转义"

# 1.5 HTML → docx 转换: 合法 zip 结构 + 文本保留 + data URI 图片内嵌
import base64 as b64mod
import zipfile as zipfile_mod

PIXEL = (
    b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR"
    + (64).to_bytes(4, "big") + (48).to_bytes(4, "big")
    + b"\x08\x06\x00\x00\x00" + (0).to_bytes(4, "big")
    + b"IEND\xaeB`\x82"
)
img_data_uri = "data:image/png;base64," + b64mod.b64encode(PIXEL).decode()
html3 = build_backup_html(
    "带图", [("模板", "<p>文字内容A</p><img src='%s'><p>文字内容B</p>" % img_data_uri, True)]
)
docx_bytes = build_docx_from_html(html3)
with zipfile_mod.ZipFile(__import__("io").BytesIO(docx_bytes)) as zf:
    names = zf.namelist()
    assert "[Content_Types].xml" in names, "缺 Content_Types"
    assert "word/document.xml" in names, "缺 document.xml"
    media = [n for n in names if n.startswith("word/media/")]
    assert len(media) == 1 and media[0].endswith(".png"), "应内嵌 1 张 PNG 图片"
    doc_xml = zf.read("word/document.xml").decode("utf-8")
    assert "文字内容A" in doc_xml and "文字内容B" in doc_xml, "docx 丢失文本"
    assert "r:embed=" in doc_xml, "docx 图片缺少 r:embed 引用"
assert docx_bytes[:2] == b"PK", "docx 不是合法 zip"

# 2. doc_url 提取
assert doc_url({"url": "https://docs.qq.com/doc/abc"}) == "https://docs.qq.com/doc/abc"
assert doc_url({"ID": "xyz"}) == "https://docs.qq.com/doc/xyz"
assert doc_url({"id": "zzz"}) == "https://docs.qq.com/doc/zzz"

# 3. 客户端全流程 (mock urllib.request.urlopen)
def fake_urlopen(req, timeout=None):
    url = req.full_url if hasattr(req, "full_url") else str(req)
    if "app-account-token" in url:
        body = {"access_token": "tok1", "user_id": "u1", "expires_in": 3600}
    elif url.startswith("https://cos.example.com/"):
        body = {}
    elif "upload-url" in url:
        body = {"data": {"COSPutURL": "https://cos.example.com/x", "COSFileKey": "k1"}}
    elif "async-import" in url:
        body = {"data": {"progressQueryID": "p1"}}
    elif "import-progress" in url:
        body = {"data": {"ID": "doc123", "url": "https://docs.qq.com/doc/doc123"}}
    elif "/folders" in url:
        body = {"data": {"list": []}}
    else:
        body = {}
    payload = json.dumps(body).encode("utf-8")

    class Resp:
        status = 200

        def __init__(self, b):
            self._b = b

        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

        def read(self):
            return self._b

    return Resp(payload)


client = TencentDocsClient("cid", "csec")
with mock.patch("urllib.request.urlopen", side_effect=fake_urlopen) as m:
    client.ping()  # 连接测试不抛错
    url = client.upload_html("<h1>备份</h1>", doc_name="备份测试")
    # 预导入接口的 fileName 必须带受支持扩展名 (.docx), 而非 .html
    import urllib.parse as up

    saw_upload_url = False
    for call in m.call_args_list:
        req = call.args[0] if call.args else call.kwargs.get("req")
        u = req.full_url if hasattr(req, "full_url") else str(req)
        if "upload-url" in u:
            saw_upload_url = True
            body = req.data if hasattr(req, "data") and req.data else b""
            params = up.parse_qs(body.decode("utf-8", "replace"))
            fname = params.get("fileName", [""])[0]
            assert fname.endswith(".docx"), f"预导入 fileName 应为 .docx, 实际: {fname}"
    assert saw_upload_url, "未调用预导入接口"
assert url == "https://docs.qq.com/doc/doc123", f"URL 提取异常: {url}"
assert client._access_token == "tok1", "token 未缓存"

# 3.5 直用 Access Token 模式 (JWT): 不请求换取接口, 直接用 token
JWT = (
    "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9."
    "eyJjbHQiOiJmNWFjZTNiODIxMmU0NjMyYmVhNDJlMmFhODFjODczMCIsInR5cCI6MSwi"
    "ZXhwIjoxNzkwMDUxMjc0LjkxNTA0NiwiaWF0IjoxNzg3NDU5Mjc0LjkxNTA0Niwic3Vi"
    "IjoiN2M3NWE0ZjRhYmQxNDM1NGI1NWZlNjFmNjdlODc1MmYifQ."
    "Oq0T7SSLhAi-M3Br4MRwHBowW7eiWAz8cXpsshLVkKs"
)
claims = parse_jwt_payload(JWT)
assert claims.get("clt") == "f5ace3b8212e4632bea42e2aa81c8730", "clt 提取失败"
assert claims.get("sub") == "7c75a4f4abd14354b55fe61f67e8752f", "sub 提取失败"
assert claims.get("exp", 0) > 0, "exp 缺失"
assert parse_jwt_payload("not-a-jwt") == {}, "非法 token 应返回空 dict"

td_client = TencentDocsClient(access_token=JWT)
assert td_client.client_id == "f5ace3b8212e4632bea42e2aa81c8730", "直用模式应自动提取 client_id"
assert td_client._open_id == "7c75a4f4abd14354b55fe61f67e8752f", "直用模式应自动提取 open_id"

# 3.6 显式 open_id 优先于 JWT 提取; 普通模式显式传入不被换取响应覆盖
td_client2 = TencentDocsClient(access_token=JWT, open_id="custom-open-id")
assert td_client2._open_id == "custom-open-id", "显式 open_id 应优先于 JWT sub"
td_client3 = TencentDocsClient("cid", "csec", open_id="manual-open-id")
assert td_client3._open_id == "manual-open-id", "普通模式应保留显式 open_id"


def fake_urlopen_no_uid(req, timeout=None):
    """换取 token 响应不含 user_id/open_id (真实场景可能出现)"""
    url = req.full_url if hasattr(req, "full_url") else str(req)
    if "app-account-token" in url:
        body = {"access_token": "tok2", "expires_in": 3600}
    else:
        body = {}
    payload = json.dumps(body).encode("utf-8")

    class Resp:
        status = 200

        def __init__(self, b):
            self._b = b

        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

        def read(self):
            return self._b

    return Resp(payload)


with mock.patch("urllib.request.urlopen", side_effect=fake_urlopen_no_uid):
    td_client3._get_access_token()
assert td_client3._open_id == "manual-open-id", "换取响应缺 open_id 时不应覆盖显式值"
assert td_client3._access_token == "tok2", "普通模式换取 token 应生效"
with mock.patch("urllib.request.urlopen", side_effect=fake_urlopen) as m:
    td_client.ping()  # 直用 token, 不触发 app-account-token 换取
    called = [u.full_url if hasattr(u, "full_url") else str(u) for u in m.call_args_list]
    assert not any("app-account-token" in u for u in called), "直用模式不应请求换取 token"
    url2 = td_client.upload_html("<h1>直用备份</h1>", doc_name="直用备份")
assert url2 == "https://docs.qq.com/doc/doc123", "直用模式上传异常"
assert "有效期" in td_client.token_expire_hint, "应给出有效期提示"

# 4. 设置页入口
from app.pages.settings_page import SettingsPage

sp = SettingsPage()
assert sp.td_client_id is not None and sp.td_client_secret is not None, "缺凭证输入框"
assert sp.td_access_token is not None, "缺 Access Token 输入框"
assert sp.td_open_id is not None, "缺 Open ID 输入框"
assert sp.td_backup_btn.text() == "☁ 一键备份配置到腾讯文档"
assert sp.td_test_btn.text() == "🔌 测试连接"
# 无凭证: 测试连接应提示且不启动线程
sp.td_access_token.setText("")
sp.td_client_id.setText("")
sp.td_client_secret.setText("")
sp._td_test()
assert sp.td_thread is None, "无凭证不应启动线程"
assert "请填写" in sp.td_status.text(), "应提示填写凭证"
# 直用 Access Token: 填 JWT 即可启动线程 (mock urlopen)
with mock.patch("urllib.request.urlopen", side_effect=fake_urlopen):
    sp.td_access_token.setText(JWT)
    sp.td_client_id.setText("")
    sp.td_client_secret.setText("")
    assert sp._start_td_thread("ping"), "直用 token 应能启动线程"
    sp.td_thread.wait(10000)
    for _ in range(200):
        app.processEvents()
        if sp.td_thread is None:
            break
        import time

        time.sleep(0.01)
assert sp.td_thread is None, "直用模式线程结束后引用应清空"
assert "连接成功" in sp.td_status.text(), "直用模式应显示连接成功"
assert "Access Token 有效期" in sp.td_status.text(), "直用模式应显示有效期提示"
# 有凭证: 启动线程 (mock urlopen 使其 run 不真实联网)
with mock.patch("urllib.request.urlopen", side_effect=fake_urlopen):
    sp.td_client_id.setText("cid")
    sp.td_client_secret.setText("csec")
    assert sp._start_td_thread("ping"), "应能启动线程"
    sp.td_thread.wait(10000)
    for _ in range(200):
        app.processEvents()
        if sp.td_thread is None:
            break
        import time

        time.sleep(0.01)
assert sp.td_thread is None, "线程结束后引用应清空"
assert "连接成功" in sp.td_status.text(), "应显示连接成功"

# 5. 文本润色页入口
from app.pages.text_polish_page import TextPolishPage

tp = TextPolishPage()
assert tp.td_backup_btn.text() == "☁ 备份到腾讯文档"
# 无凭证: 提示 (先清空 config 中的凭证, 不受 config.json 实际值影响)
tp.cfg.config.setdefault("tencent_docs", {}).pop("client_id", None)
tp.cfg.config.setdefault("tencent_docs", {}).pop("client_secret", None)
tp.cfg.config.setdefault("tencent_docs", {}).pop("access_token", None)
tp._td_backup_templates()
assert tp.td_thread is None
assert "未配置腾讯文档凭证" in tp.status_label.text(), "应提示先配置凭证"
# 有凭证 (Client ID/Secret): 启动备份线程 (mock)
tp.cfg.config.setdefault("tencent_docs", {})["client_id"] = "cid"
tp.cfg.config.setdefault("tencent_docs", {})["client_secret"] = "csec"
tp.cfg.config.setdefault("tencent_docs", {}).pop("access_token", None)
with mock.patch("urllib.request.urlopen", side_effect=fake_urlopen):
    tp._td_backup_templates()
    assert tp.td_thread is not None, "应启动备份线程"
    tp.td_thread.wait(15000)
    for _ in range(200):
        app.processEvents()
        if tp.td_thread is None:
            break
        import time

        time.sleep(0.01)
assert tp.td_thread is None, "备份线程结束后引用应清空"
assert "备份成功" in tp.status_label.text(), "应显示备份成功"
# 直用 Access Token: 仅填 JWT 也能备份
tp.cfg.config["tencent_docs"] = {"access_token": JWT}
with mock.patch("urllib.request.urlopen", side_effect=fake_urlopen):
    tp._td_backup_templates()
    assert tp.td_thread is not None, "直用 token 应能启动备份线程"
    tp.td_thread.wait(15000)
    for _ in range(200):
        app.processEvents()
        if tp.td_thread is None:
            break
        import time

        time.sleep(0.01)
assert tp.td_thread is None, "直用 token 备份线程结束后引用应清空"
assert "备份成功" in tp.status_label.text(), "直用模式应显示备份成功"

print("ALL PASS: 腾讯文档同步 (客户端流程/HTML构建/设置页/润色页)")

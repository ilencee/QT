# -*- coding: utf-8 -*-
"""诊断腾讯文档真实 API 调用: 用 config.json 的真实凭证实测 ping / upload 流程, 打印每一步的真实报错"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.core.tencent_docs import (  # noqa: E402
    TencentDocsClient,
    TencentDocsError,
    build_config_backup_html,
)

ROOT = Path(__file__).resolve().parents[1]
config = json.loads((ROOT / "config.json").read_text(encoding="utf-8"))
td = config.get("tencent_docs", {}) or {}
print("凭证: client_id=%s" % td.get("client_id", ""))
print("     open_id=%s" % td.get("open_id", ""))
print("     access_token=%s..." % str(td.get("access_token", ""))[:40])
print("     client_secret 已配置: %s" % bool(td.get("client_secret")))

client = TencentDocsClient(
    str(td.get("client_id", "")),
    str(td.get("client_secret", "")),
    access_token=str(td.get("access_token", "")),
    open_id=str(td.get("open_id", "")),
)
print("解析后: client_id=%s open_id=%s" % (client.client_id, client._open_id))
print("有效期提示: %s" % client.token_expire_hint)
print()

# 1) ping 根目录
print("=== 1) ping: GET /openapi/drive/v2/folders ===")
try:
    resp = client.ping()
    print("ping 成功: ret=%s msg=%s" % (resp.get("ret"), resp.get("msg")))
    data = resp.get("data")
    if isinstance(data, dict) and "list" in data:
        print("根目录共 %d 项" % len(data["list"]))
    else:
        print("data 片段:", json.dumps(data, ensure_ascii=False)[:300])
except TencentDocsError as e:
    print("❌ ping 失败:", str(e)[:500])
    sys.exit(1)
except Exception as e:  # noqa: BLE001
    print("❌ ping 异常:", repr(e)[:500])
    sys.exit(1)

# 2) 实际备份 (产生一个新文档)
print()
print("=== 2) 实际备份 upload_html ===")
try:
    html = build_config_backup_html(config, "诊断备份")
    url = client.upload_html(html, doc_name="诊断备份-测试")
    print("✅ 备份成功:", url)
except TencentDocsError as e:
    print("❌ 备份失败:", str(e)[:600])
except Exception as e:  # noqa: BLE001
    print("❌ 备份异常:", repr(e)[:600])

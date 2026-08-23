# 日志示例：三个典型场景

> 所有示例均来自 `scripts/smoke_logger.py` 的真实运行输出（`logs/smoke.log`）。
> 每行是一条 JSON，可按行解析、按字段检索。

---

## 场景一：正常操作链路（trace_id 贯穿 + 操作上下文）

一次「文本润色」操作：从开始、AI 调用、到保存成功，所有日志共享同一个
`trace_id`，`context` 自动附带 `bind()` 注入的操作上下文（用户/会话）。

```json
{"trace_id": "13445961742770", "timestamp": "2026-08-23T13:44:59.988+08:00", "level": "INFO", "service": "work_assistant", "file": "smoke_logger.py", "line": 39, "func": "demo_normal_flow", "message": "开始处理润色请求", "context": {"doc_type": "工艺要求", "chip": "中微爱芯"}, "duration_ms": null, "tag": null, "stack_trace": null, "thread": "MainThread", "memory_mb": 20.4}
{"trace_id": "13445961742770", "timestamp": "2026-08-23T13:44:59.988+08:00", "level": "DEBUG", "service": "work_assistant", "file": "smoke_logger.py", "line": 42, "func": "demo_normal_flow", "message": "→ 开始: 调用 DeepSeek 润色", "context": {"user": "alice", "session": "S-1001"}, "duration_ms": null, "tag": null, "stack_trace": null, "thread": "MainThread", "memory_mb": 20.5}
{"trace_id": "13445961742770", "timestamp": "2026-08-23T13:45:00.013+08:00", "level": "INFO", "service": "work_assistant", "file": "smoke_logger.py", "line": 42, "func": "demo_normal_flow", "message": "← 完成: 调用 DeepSeek 润色", "context": {"user": "alice", "session": "S-1001"}, "duration_ms": 24.85, "tag": null, "stack_trace": null, "thread": "MainThread", "memory_mb": 20.5}
{"trace_id": "13445961742770", "timestamp": "2026-08-23T13:45:00.014+08:00", "level": "INFO", "service": "work_assistant", "file": "smoke_logger.py", "line": 44, "func": "demo_normal_flow", "message": "AI 响应已解析", "context": {"user": "alice", "session": "S-1001", "chars": 1280, "cost_fen": 3}, "duration_ms": null, "tag": null, "stack_trace": null, "thread": "MainThread", "memory_mb": 20.5}
{"trace_id": "13445961742770", "timestamp": "2026-08-23T13:45:00.014+08:00", "level": "INFO", "service": "work_assistant", "file": "smoke_logger.py", "line": 46, "func": "demo_normal_flow", "message": "模板保存成功", "context": {"doc_type": "工艺要求", "saved": true}, "duration_ms": null, "tag": null, "stack_trace": null, "thread": "MainThread", "memory_mb": 20.5}
```

**排查用法**：`trace_id=13445961742770` 一条命令捞出整条链路：

```bash
findstr "13445961742770" logs\app.log
```

---

## 场景二：异常捕获（ERROR + 完整堆栈 + 脱敏参数）

腾讯文档导入失败：`level=ERROR`，`stack_trace` 是完整 Python 堆栈（含抛出位置
`smoke_logger.py:56`），`context` 中的 `token`（键名敏感）、URL 参数、身份证、
银行卡全部自动打码；手机号（`user_phone`）也按规则脱敏。

```json
{"trace_id": "13445961742770", "timestamp": "2026-08-23T13:45:00.015+08:00", "level": "ERROR", "service": "work_assistant", "file": "smoke_logger.py", "line": 58, "func": "fetch_doc", "message": "导入文档失败", "context": {"url": "https://docs.qq.com/import?token=***", "token": "***", "user_phone": "13812345678", "id_card": "110101********1234", "bank_card": "6222**********4567", "retry": 2}, "duration_ms": null, "tag": null, "stack_trace": "Traceback (most recent call last):\n  File \"c:\\Users\\86249\\Desktop\\Github\\QT\\scripts\\smoke_logger.py\", line 56, in fetch_doc\n    raise ConnectionError(\"连接超时: 无法访问腾讯文档服务器\")\nConnectionError: 连接超时: 无法访问腾讯文档服务器", "thread": "MainThread", "memory_mb": 20.6}
```

> 说明：`user_phone` 键名未命中敏感键，但值 `13812345678` 命中手机号正则
> `1[3-9]` 开头 11 位 → 保留前 3 后 4。`token` 键名直接整体打码 `***`。

**排查用法**：查某段时间所有 ERROR + 堆栈，一秒定位根因：

```bash
findstr /C:"\"level\": \"ERROR\"" logs\app.log
```

---

## 场景三：性能瓶颈（SLOW_QUERY / SLOW_API 自动 WARN）

烧录软件扫描超过 `query_ms=10ms`（示例调小）自动升级 WARNING + `tag=SLOW_QUERY`；
COS 上传超过 `api_ms=50ms` 自动 `tag=SLOW_API`。生产阈值分别为 500ms / 3s。

```json
{"trace_id": "13445961742770", "timestamp": "2026-08-23T13:45:00.016+08:00", "level": "DEBUG", "service": "work_assistant", "file": "smoke_logger.py", "line": 78, "func": "demo_slow", "message": "→ 开始: 扫描已安装烧录软件", "context": null, "duration_ms": null, "tag": null, "stack_trace": null, "thread": "MainThread", "memory_mb": 20.6}
{"trace_id": "13445961742770", "timestamp": "2026-08-23T13:45:00.041+08:00", "level": "WARNING", "service": "work_assistant", "file": "smoke_logger.py", "line": 78, "func": "demo_slow", "message": "← 完成: 扫描已安装烧录软件", "context": null, "duration_ms": 24.85, "tag": "SLOW_QUERY", "stack_trace": null, "thread": "MainThread", "memory_mb": 20.6}
{"trace_id": "13445961742770", "timestamp": "2026-08-23T13:45:00.041+08:00", "level": "DEBUG", "service": "work_assistant", "file": "smoke_logger.py", "line": 80, "func": "demo_slow", "message": "→ 开始: 上传固件到 COS", "context": null, "duration_ms": null, "tag": null, "stack_trace": null, "thread": "MainThread", "memory_mb": 20.6}
{"trace_id": "13445961742770", "timestamp": "2026-08-23T13:45:00.134+08:00", "level": "WARNING", "service": "work_assistant", "file": "smoke_logger.py", "line": 80, "func": "demo_slow", "message": "← 完成: 上传固件到 COS", "context": null, "duration_ms": 92.64, "tag": "SLOW_API", "stack_trace": null, "thread": "MainThread", "memory_mb": 20.6}
```

**排查用法**：性能问题直接捞 SLOW 标记 + 按 `duration_ms` 排序找最慢操作：

```bash
findstr "SLOW_API" logs\app.log
```

---

## 附加：多线程 trace_id 独立 + DEBUG 采样

两个后台线程各自 `set_trace_id("thr-A"/"thr-B")`，互不串扰；主线程 `DEBUG`
采样率 0.1 时 1000 次调用实际落盘 90~101 条（约 10%）。

```json
{"trace_id": "thr-A", "timestamp": "2026-08-23T13:45:00.135+08:00", "level": "DEBUG", "service": "work_assistant", "file": "smoke_logger.py", "line": 91, "func": "worker", "message": "线程 A 处理第 0 项", "context": {"item": 0}, "duration_ms": null, "tag": null, "stack_trace": null, "thread": "Thread-1", "memory_mb": 20.7}
{"trace_id": "thr-B", "timestamp": "2026-08-23T13:45:00.135+08:00", "level": "DEBUG", "service": "work_assistant", "file": "smoke_logger.py", "line": 91, "func": "worker", "message": "线程 B 处理第 0 项", "context": {"item": 0}, "duration_ms": null, "tag": null, "stack_trace": null, "thread": "Thread-2", "memory_mb": 20.7}
```

## 字段说明（固定 14 列）

| 字段 | 类型 | 说明 |
|---|---|---|
| trace_id | str | 线程局部链路 ID，贯穿一次操作 |
| timestamp | str | ISO8601，毫秒精度，含时区偏移 |
| level | str | DEBUG / INFO / WARNING / ERROR / FATAL |
| service | str | 服务名（默认 work_assistant） |
| file | str | 代码文件名（自动提取） |
| line | int | 代码行号（自动提取） |
| func | str | 函数名（自动提取） |
| message | str | 日志消息（已脱敏） |
| context | obj | 业务上下文（嵌套 dict/list 递归脱敏） |
| duration_ms | float | 耗时（仅 timed 系列） |
| tag | str | SLOW_QUERY / SLOW_API / EXCEPTION 等标记 |
| stack_trace | str | 完整异常堆栈（仅异常日志） |
| thread | str | 线程名 |
| memory_mb | float | 当前进程内存占用 |

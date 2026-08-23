# Bug 排查 SOP：基于结构化日志 5 分钟定位

> 配套代码：`app/core/logger.py`（结构化 JSON 日志）
> 配套配置：`config/logging.example.json`（并入 config.json 的 `logging` 段）
> 配套示例：`docs/log-examples.md`

## 一、日志文件位置

| 运行方式 | 日志路径 |
|---|---|
| 源码运行 | `<项目根>/logs/app.log` |
| 打包 exe | `<exe 同目录>/logs/app.log` |

滚动策略：单文件最大 10MB，保留 5 个（`app.log.1` … `app.log.5`）。
Bug 复现后第一时间复制整个 `logs/` 目录。

---

## 二、标准排查流程（5 分钟内）

### 第 1 步：锁定时间段（30 秒）

Bug 发生在何时？按时间过滤：

```bash
# 取 2026-08-23 13:44~13:46 之间的日志
findstr /C:"2026-08-23T13:4[4-6]" logs\app.log
```

### 第 2 步：捞 ERROR/FATAL 及堆栈（1 分钟）

```bash
# 全部错误 + 异常堆栈
findstr /C:"\"level\": \"ERROR\"" logs\app.log
findstr /C:"\"level\": \"FATAL\"" logs\app.log
```

一条 ERROR 已足够定位：

- `file` / `line` / `func` → 出错代码位置（打开文件跳转该行）
- `stack_trace` → 完整调用链，看最内层抛异常的栈帧
- `context` → 该次调用的输入参数（已脱敏）
- `thread` → 前台主线程 or 后台工作线程

### 第 3 步：按 trace_id 还原整条操作链路（1 分钟）

从 ERROR 行取出 `trace_id`，把这条操作从开始到失败的所有日志捞出来：

```bash
findstr "<trace_id>" logs\app.log
```

顺序看 `→ 开始 … → 完成/异常`，确定失败发生在链路的哪一步、哪一行。

### 第 4 步：区分错误类别（1 分钟）

| 现象 | 查什么 |
|---|---|
| 某功能直接崩 / 弹异常 | 该时间段 ERROR + stack_trace |
| 功能无反应 / 卡住 | SLOW_QUERY / SLOW_API 标记 + duration_ms |
| 偶发失败 / 时好时坏 | 同 trace_id 链路 + 前后对比正常操作 |
| 数据不对 / 逻辑错 | 该操作 INFO/DEBUG 的 context 入参 |
| 内存持续上涨 | memory_mb 字段随时间的趋势 |

### 第 5 步：给出结论与修复（1 分钟）

格式：`文件:行号` + `根因` + `触发参数` + `修复建议`。

---

## 三、三个真实排查示例

### 示例 A：AI 润色请求偶尔失败

```
用户反馈：润色偶尔报错，重试又好了。
```

```bash
findstr "SLOW_API" logs\app.log        # 发现 AI 请求 >3s 被标记
findstr /C:"\"level\": \"ERROR\"" logs\app.log | findstr "deepseek"
```

**结论**：`deepseek_client.py:88` 网络超时（`timeout=30`），stack_trace 显示
`requests.exceptions.ReadTimeout`；context 显示 `model` / `input_chars`。
**修复**：超时重试 + 指数退避；超时上限 30s 改为可配置。

### 示例 B：切到烧录页界面卡死

```
用户反馈：点「烧录」页要转圈很久。
```

```bash
findstr "SLOW_QUERY" logs\app.log
```

**结论**：`programming_software_page.py:412` 扫描已安装软件耗时 8.2s
（`duration_ms: 8203.5`，tag=SLOW_QUERY）。**根因**：注册表扫描在 UI 线程同步执行。
**修复**：改后台线程 + 信号回填（项目已有 `detection_done` 模式可复用）。

### 示例 C：保存模板后图片丢失

```
用户反馈：插了图片点保存，重启后图片没了。
```

```bash
findstr "保存模板" logs\app.log
```

**结论**：`text_polish_page.py:610` 保存时 `template` 字段为空
（context: `{"doc_type": "工艺要求", "img_count": 0}`）。**根因**：dirty 检测把
仅含图片的模板误判为未修改（`\ufffc` 归一化问题）。**修复**：`_template_dirty()`
将图片占位归一化为 `" [图片] "` 再比较。

---

## 四、日志等级规范（写入代码前先定级）

| 等级 | 何时用 | 示例 |
|---|---|---|
| DEBUG | 详细过程、变量、采样输出 | `→ 开始: 调用 DeepSeek 润色` |
| INFO | 关键业务节点、成功/失败结果 | `模板保存成功`, `应用启动` |
| WARNING | 可恢复异常、性能降级、兼容处理 | `SLOW_QUERY`, `配置缺失用默认值` |
| ERROR | 异常捕获（必须带完整堆栈） | `导入文档失败` + exc_info |
| FATAL | 不可恢复、进程即将退出 | 主配置损坏无法启动 |

**强制约定**：

1. `except` 分支**必须**记 `log.error(..., exc_info=True)`，否则视为漏日志。
2. 慢操作**必须**用 `log.timed_query() / log.timed_api()` 包裹，不要手写时间。
3. 一次用户操作的入口处 `set_trace_id()`（后台线程同理），保证链路可回溯。
4. 日志 message 用中文短句 + context 传结构化参数，**禁止**把敏感值拼进 message。

---

## 五、日常维护

```bash
# 查看今天所有 WARNING 以上
findstr /C:"\"level\": \"WARNING\"" /C:"\"level\": \"ERROR\"" /C:"\"level\": \"FATAL\"" logs\app.log

# 最慢的 5 个操作 (PowerShell)
Get-Content logs\app.log | ConvertFrom-Json | Where-Object { $_.duration_ms } |
  Sort-Object duration_ms -Descending | Select-Object -First 5

# 内存趋势 (PowerShell)
Get-Content logs\app.log | ConvertFrom-Json | Select-Object timestamp, memory_mb | Format-Table

# 触发诊断模式 (临时把 DEBUG 采样率调到 1.0 复现细节)
# 修改 config.json -> logging.level = "DEBUG", logging.debug_sample_rate = 1.0
```

### 日志不落盘 / 没内容时

1. 确认 `config.json` 是否含 `logging` 段；没有则按 `config/logging.example.json` 补上。
2. 确认 `<应用根>/logs/` 目录存在且可写。
3. 源码运行看控制台是否有 `--- Logging error ---`（此时 stderr 有真实 traceback）。

"""
结构化 JSON 日志系统 (生产级)
=============================
核心目标: 当软件出现 Bug 时, 能在 5 分钟内通过日志定位到具体代码位置、
输入参数和根因。

设计要点
--------
1. 结构化输出: 每行一条 JSON, 机器可解析, 字段固定 (见 _FIELDS 说明)。
2. 上下文贯穿: 线程局部 (ThreadLocal) trace_id 贯穿一次操作链路,
   多线程 (Qt 信号/后台线程) 各线程独立 trace_id。
3. 零成本定位: file / line / func 由调用栈自动提取, 业务代码无需手工填写。
4. 自动脱敏: 密码 / Token / 身份证 / 手机号 / 银行卡 在写盘前自动打码。
5. 成本控制: DEBUG 级日志按比例采样, INFO 及以上全量记录。
6. 性能监控: timed / timed_query / timed_api 上下文管理器自动记录耗时,
   超过阈值自动升级为 WARNING 并打 SLOW_QUERY / SLOW_API 标记。
7. 异常必记: catch 上下文 / exc_info 自动附带完整堆栈与脱敏后的输入参数。
8. 内存监控: 每条日志附带当前进程内存占用 (可选, 默认开)。

用法速览
--------
    from app.core.logger import setup_logging, get_logger, set_trace_id

    setup_logging(cfg.get("logging"))          # 程序入口初始化一次
    log = get_logger("text_polish")            # 按模块获取 logger

    log.info("模板保存成功", doc_type="工艺要求", chip="中微爱芯")
    log.error("AI 请求失败", url=..., exc_info=True)   # 自动堆栈

    with log.timed_query("查询配置"):          # 慢操作自动 WARN
        do_something()

    try:
        ...
    except Exception:
        log.error("保存模板异常", context={"doc_type": t}, exc_info=True)
"""

import json
import io
import logging
import logging.handlers
import os
import random
import re
import sys
import threading
import time
import traceback
from contextlib import contextmanager
from datetime import datetime
from functools import wraps
from pathlib import Path
from typing import Optional, Union

# ======================================================================
# 常量
# ======================================================================

SERVICE = "work_assistant"          # 服务名, 可被 config 覆盖
TRACE_ID_ATTR = "_trace_id"         # 日志记录上 trace_id 的属性名
DEFAULT_SLOW_QUERY_MS = 500         # 数据库/本地查询类操作阈值 (ms)
DEFAULT_SLOW_API_MS = 3000          # 外部 API 调用阈值 (ms)
DEFAULT_DEBUG_SAMPLE_RATE = 0.1     # DEBUG 采样率: 只记录 10%

# 单条日志固定字段 (输出顺序固定, 便于人工阅读/机器解析)
_JSON_KEYS = (
    "trace_id", "timestamp", "level", "service",
    "file", "line", "func", "message",
    "context", "duration_ms", "tag",
    "stack_trace", "thread", "memory_mb",
)

# 默认配置: 可通过 setup_logging(config) 传入 dict 覆盖任意键
DEFAULT_CONFIG = {
    "enabled": True,                # 总开关
    "level": "INFO",                # 最低级别: DEBUG/INFO/WARNING/ERROR/FATAL
    "service": SERVICE,
    "dir": "logs",                  # 日志目录 (相对应用根目录)
    "file": "app.log",              # 日志文件名 (RotatingFileHandler 滚动)
    "max_bytes": 10 * 1024 * 1024,  # 单文件最大 10MB
    "backup_count": 5,              # 保留 5 个滚动文件
    "console": True,                # 是否同时输出到控制台
    "debug_sample_rate": DEFAULT_DEBUG_SAMPLE_RATE,  # DEBUG 采样率 (0~1)
    "memory": True,                 # 每条日志是否附带内存占用
    "slow": {
        "query_ms": DEFAULT_SLOW_QUERY_MS,
        "api_ms": DEFAULT_SLOW_API_MS,
    },
    "mask": {                       # 脱敏开关 (逐项可关)
        "enabled": True,
        "password": True,
        "token": True,
        "id_card": True,
        "phone": True,
        "bank_card": True,
    },
    "encoding": "utf-8",
}

# 敏感键名 (context 字典中 key 匹配即整体打码)
_SENSITIVE_KEYS = re.compile(
    r"(?i)(password|passwd|pwd|secret|token|api[_-]?key|access[_-]?token|"
    r"refresh[_-]?token|authorization|apikey|sign|private[_-]?key|cookie)"
)

# message 字符串内嵌的 key=value / key:value / key="value" 形式的敏感参数
_KV_RE = re.compile(
    r"(?i)(password|passwd|pwd|secret|token|api[_-]?key|access[_-]?token|"
    r"refresh[_-]?token|authorization)\s*([=:]\s*)([\"']?)[^\s\"',;}{]+"
)

# URL 查询串中的敏感参数 (?token=xxx&key=yyy)
_QUERY_PARAM_RE = re.compile(
    r"(?i)([?&](?:token|access[_-]?token|sign|key|secret|password|api[_-]?key)=)[^&\s]+"
)

# 18 位身份证: 保留前 6 后 4
_ID_CARD_RE = re.compile(r"(?<!\d)(\d{6})\d{8}(\d{3}[\dXx])(?!\d)")
# 中国大陆手机号: 保留前 3 后 4
_PHONE_RE = re.compile(r"(?<!\d)(1[3-9])(\d{4})\d{4}(?!\d)")
# 银行卡 16~19 位: 保留前 4 后 4
_BANK_CARD_RE = re.compile(r"(?<!\d)(\d{4})\d{8,11}(\d{4})(?!\d)")

# 单例注册表: logger 名称 -> JsonLogger
_loggers: dict = {}
# 全局配置 (setup_logging 后生效)
_g_config: dict = dict(DEFAULT_CONFIG)
# 线程局部: trace_id 与操作链路上下文
_tls = threading.local()


# ======================================================================
# 内存占用 (Windows / Linux 通用, psutil 优先, ctypes 兜底)
# ======================================================================

def _get_memory_mb() -> Optional[float]:
    """返回当前进程占用内存 (MB), 失败返回 None。"""
    try:
        import psutil  # 可选依赖, 有则用
        return round(psutil.Process().memory_info().rss / 1024 / 1024, 1)
    except Exception:
        pass
    if os.name == "nt":
        try:
            import ctypes
            from ctypes import wintypes

            class _PMC(ctypes.Structure):  # PROCESS_MEMORY_COUNTERS
                _fields_ = [
                    ("cb", wintypes.DWORD),
                    ("PageFaultCount", wintypes.DWORD),
                    ("PeakWorkingSetSize", ctypes.c_size_t),
                    ("WorkingSetSize", ctypes.c_size_t),
                    ("QuotaPeakPagedPoolUsage", ctypes.c_size_t),
                    ("QuotaPagedPoolUsage", ctypes.c_size_t),
                    ("QuotaPeakNonPagedPoolUsage", ctypes.c_size_t),
                    ("QuotaNonPagedPoolUsage", ctypes.c_size_t),
                    ("PagefileUsage", ctypes.c_size_t),
                    ("PeakPagefileUsage", ctypes.c_size_t),
                ]

            h = ctypes.windll.kernel32.OpenProcess(0x0400 | 0x0010, False, os.getpid())
            if h:
                try:
                    c = _PMC()
                    c.cb = ctypes.sizeof(_PMC)
                    if ctypes.windll.psapi.GetProcessMemoryInfo(h, ctypes.byref(c), c.cb):
                        return round(c.WorkingSetSize / 1024 / 1024, 1)
                finally:
                    ctypes.windll.kernel32.CloseHandle(h)
        except Exception:
            pass
    return None


# ======================================================================
# trace_id (线程局部)
# ======================================================================

def _new_trace_id() -> str:
    """生成 trace_id: 时间戳(秒) + 线程 id + 随机串, 全局近似唯一。"""
    return (datetime.now().strftime("%H%M%S")
            + f"{threading.get_ident():x}"
            + f"{random.randint(0, 0xFFFF):04x}")


def set_trace_id(trace_id: Optional[str] = None) -> str:
    """为当前线程设置 trace_id (未传则自动生成), 返回最终值。

    用于一次操作链路的起点: 操作内所有日志共享同一 trace_id。
    """
    if trace_id is None:
        trace_id = _new_trace_id()
    _tls.trace_id = trace_id
    return trace_id


def get_trace_id() -> Optional[str]:
    """获取当前线程的 trace_id, 没有则返回 None (不自动生成)。"""
    return getattr(_tls, "trace_id", None)


def get_or_create_trace_id() -> str:
    """获取当前线程 trace_id, 没有则自动生成 (保证每条日志都有)。"""
    tid = getattr(_tls, "trace_id", None)
    if tid is None:
        tid = _new_trace_id()
        _tls.trace_id = tid
    return tid


def clear_trace_id() -> None:
    """清除当前线程的 trace_id (线程池归还线程前调用)。"""
    _tls.trace_id = None


# ======================================================================
# 脱敏
# ======================================================================

def mask_text(text: str) -> str:
    """对文本做正则脱敏: key=value 敏感参数 / URL 参数 / 身份证 / 手机号 / 银行卡。"""
    m = _g_config.get("mask", {})
    if not m.get("enabled", True):
        return text
    text = _KV_RE.sub(lambda mm: f"{mm.group(1)}{mm.group(2)}***", text)
    text = _QUERY_PARAM_RE.sub(r"\1***", text)
    if m.get("id_card", True):
        text = _ID_CARD_RE.sub(r"\1********\2", text)
    if m.get("phone", True):
        text = _PHONE_RE.sub(r"\1****\2", text)
    if m.get("bank_card", True):
        text = _BANK_CARD_RE.sub(r"\1**********\2", text)
    return text


def _mask_value(key, value):
    """按 key 是否为敏感键决定是否掩码 value。"""
    if isinstance(key, str) and _SENSITIVE_KEYS.search(key):
        return "***"
    if isinstance(value, str):
        return mask_text(value)
    return value


def mask_context(ctx: dict) -> dict:
    """递归脱敏 context 字典 (嵌套 dict/list 一并处理)。"""
    m = _g_config.get("mask", {})
    if not m.get("enabled", True):
        return ctx
    out = {}
    for k, v in ctx.items():
        if isinstance(k, str) and _SENSITIVE_KEYS.search(k):
            out[k] = "***"
        elif isinstance(v, dict):
            out[k] = mask_context(v)
        elif isinstance(v, (list, tuple)):
            out[k] = [_mask_value(k, x) if not isinstance(x, dict)
                      else mask_context(x) for x in v]
        elif isinstance(v, str):
            out[k] = mask_text(v)
        else:
            out[k] = v
    return out


# ======================================================================
# JSON Formatter: 任意 LogRecord (含第三方库) 一律输出 JSON
# ======================================================================

class JsonFormatter(logging.Formatter):
    """把 LogRecord 序列化为单行 JSON。

    兼容标准 logging: 第三方库 (urllib3/requests 等) 经由 root handler
    进来的 record 没有自定义字段时自动补默认值, 不会报错。
    """

    def format(self, record: logging.LogRecord) -> str:
        d = {
            "trace_id": getattr(record, TRACE_ID_ATTR, None) or get_or_create_trace_id(),
            "timestamp": datetime.now().astimezone().isoformat(timespec="milliseconds"),
            "level": record.levelname,
            "service": getattr(record, "service", None) or _g_config.get("service", SERVICE),
            "file": os.path.basename(record.pathname),
            "line": record.lineno,
            "func": record.funcName,
            "message": record.getMessage(),
            "context": None,
            "duration_ms": getattr(record, "duration_ms", None),
            "tag": getattr(record, "tag", None),
            "stack_trace": None,
            "thread": record.threadName,
            "memory_mb": None,
        }
        # context: 线程链路上下文 + 本次上下文合并
        ctx = getattr(record, "context", None) or {}
        tctx = getattr(_tls, "ctx_stack", None)
        if tctx:
            merged = {}
            for item in tctx.stack:
                merged.update(item)
            merged.update(ctx)
            ctx = merged
        if ctx:
            d["context"] = mask_context(ctx)
        # 耗时 / 标记
        if d["duration_ms"] is not None:
            d["duration_ms"] = round(float(d["duration_ms"]), 2)
        # 异常堆栈
        if record.exc_info and record.exc_info[0]:
            d["stack_trace"] = "".join(
                traceback.format_exception(*record.exc_info)
            ).strip()
        # message 脱敏
        if isinstance(d["message"], str):
            d["message"] = mask_text(d["message"])
        # 内存占用
        if _g_config.get("memory", True):
            d["memory_mb"] = _get_memory_mb()
        return json.dumps(
            {k: d[k] for k in _JSON_KEYS}, ensure_ascii=False, default=str
        )


# ======================================================================
# 日志器
# ======================================================================

class JsonLogger:
    """业务侧日志器: 方法即字段, file/line/func 自动提取。

    方法: debug / info / warning / error / fatal
    上下文: timed / timed_query / timed_api / catch / bind / push
    trace_id: new_trace_id / trace_id / clear_trace_id (线程局部)
    """

    def __init__(self, name: str):
        self._name = name
        # 底层仍走标准 logging, 便于统一接管第三方库日志
        self._logger = logging.getLogger(name)
        self._slow_query_ms = _g_config.get("slow", {}).get(
            "query_ms", DEFAULT_SLOW_QUERY_MS)
        self._slow_api_ms = _g_config.get("slow", {}).get(
            "api_ms", DEFAULT_SLOW_API_MS)
        self._sample_rate = float(_g_config.get("debug_sample_rate",
                                                 DEFAULT_DEBUG_SAMPLE_RATE))

    # ---- 基本信息 ----
    @property
    def name(self) -> str:
        return self._name

    # ---- 对外便捷方法 ----
    def debug(self, message: str, **context) -> None:
        self._emit(logging.DEBUG, message, context)

    def info(self, message: str, **context) -> None:
        self._emit(logging.INFO, message, context)

    def warning(self, message: str, **context) -> None:
        self._emit(logging.WARNING, message, context)

    def error(self, message: str, context=None, exc_info=False, **extra) -> None:
        """记录 ERROR。异常场景必须传 exc_info=True (自动附加完整堆栈)。"""
        ctx = dict(context) if context else {}
        ctx.update(extra)
        self._emit(logging.ERROR, message, ctx, exc_info=bool(exc_info))

    def fatal(self, message: str, context=None, exc_info=False, **extra) -> None:
        """记录 FATAL (logging.CRITICAL), 用于不可恢复错误。"""
        ctx = dict(context) if context else {}
        ctx.update(extra)
        self._emit(logging.CRITICAL, message, ctx, exc_info=bool(exc_info))

    # ---- trace_id (委托线程局部) ----
    def new_trace_id(self) -> str:
        """开始一条新的操作链路: 为当前线程重置 trace_id。"""
        return set_trace_id()

    @property
    def trace_id(self) -> Optional[str]:
        return get_trace_id()

    # ---- 操作链路上下文 ----
    def push(self, **context) -> None:
        """压入操作链路上下文: 之后所有日志自动附带这些字段, 直到 pop。"""
        stack = getattr(_tls, "ctx_stack", None)
        if stack is None:
            stack = _CtxStack()
            _tls.ctx_stack = stack
        stack.push(context)

    def pop(self) -> None:
        """弹出最近一次 push 的上下文。"""
        stack = getattr(_tls, "ctx_stack", None)
        if stack:
            stack.pop()

    @contextmanager
    def bind(self, **context):
        """with log.bind(doc_type="工艺要求"): ... 期间日志自动带这些字段。"""
        self.push(**context)
        try:
            yield
        finally:
            self.pop()

    # ---- 耗时统计 ----
    @contextmanager
    def timed(self, action: str, slow_ms=None, tag=None, level=logging.INFO,
              **context):
        """耗时统计上下文。

        with log.timed("扫描已安装烧录软件"): ...

        结束自动记一条日志: 正常 INFO + duration_ms;
        超过 slow_ms (默认取配置 query_ms) 自动升级 WARNING + tag=SLOW_QUERY。
        """
        if slow_ms is None:
            slow_ms = self._slow_query_ms
            if tag is None:
                tag = "SLOW_QUERY"
        # 进入 with 时记录业务调用位置 (contextlib 内部帧不计入)
        caller = _caller_info(_find_caller_frame(sys._getframe(1)))
        start = time.perf_counter()
        self._emit(logging.DEBUG, f"→ 开始: {action}", dict(context), caller=caller)
        try:
            yield
        finally:
            ms = (time.perf_counter() - start) * 1000
            is_slow = slow_ms is not None and ms >= slow_ms
            lvl = logging.WARNING if is_slow else level
            self._emit(lvl, f"← 完成: {action}", dict(context),
                       duration_ms=ms, tag=tag if is_slow else None, caller=caller)

    @contextmanager
    def timed_query(self, action: str, **context):
        """慢查询标记: 超过配置 query_ms (默认 500ms) 自动 WARN SLOW_QUERY。"""
        with self.timed(action, slow_ms=self._slow_query_ms,
                        tag="SLOW_QUERY", **context):
            yield

    @contextmanager
    def timed_api(self, action: str, **context):
        """慢 API 标记: 超过配置 api_ms (默认 3s) 自动 WARN SLOW_API。"""
        with self.timed(action, slow_ms=self._slow_api_ms,
                        tag="SLOW_API", **context):
            yield

    # ---- 异常捕获 ----
    @contextmanager
    def catch(self, action: str, re_raise=True, level=logging.ERROR, **context):
        """异常捕获上下文: 块内抛异常时自动记 ERROR (含堆栈/脱敏参数)。

        with log.catch("保存模板", doc_type=t, chip=c):
            do_something()

        re_raise=True (默认): 捕获后重新抛出, 保持调用方异常语义。
        """
        caller = _caller_info(_find_caller_frame(sys._getframe(1)))
        try:
            yield
        except Exception:
            self._emit(level, f"{action} 异常", dict(context),
                       exc_info=True, tag="EXCEPTION", caller=caller)
            if re_raise:
                raise

    # ---- 函数级装饰器 ----
    def log_call(self, slow_ms=None, tag=None):
        """装饰器: 自动记录函数开始(DEBUG)/结束(INFO, 含耗时)/异常(ERROR)。

        @log.log_call(slow_ms=3000, tag="SLOW_API")
        def fetch(...): ...
        """
        def deco(fn):
            # 定位到函数定义处 (而非调用点)
            path = (fn.__code__.co_filename,
                    fn.__code__.co_firstlineno, fn.__qualname__)

            @wraps(fn)
            def wrapper(*args, **kwargs):
                # 参数脱敏: self 之外的位置参数 + 全部关键字参数
                ctx = {}
                for i, a in enumerate(args[1:], 1):
                    ctx[f"arg{i}"] = _safe_repr(a)
                for k, v in kwargs.items():
                    ctx[k] = _safe_repr(v)
                start = time.perf_counter()
                self._emit(logging.DEBUG, f"→ 调用 {fn.__qualname__}",
                           dict(ctx), caller=path)
                try:
                    rv = fn(*args, **kwargs)
                except Exception:
                    ms = (time.perf_counter() - start) * 1000
                    self._emit(logging.ERROR, f"{fn.__qualname__} 异常",
                               dict(ctx), exc_info=True, duration_ms=ms,
                               tag="EXCEPTION", caller=path)
                    raise
                ms = (time.perf_counter() - start) * 1000
                is_slow = slow_ms is not None and ms >= slow_ms
                lvl = logging.WARNING if is_slow else logging.INFO
                self._emit(lvl, f"← 返回 {fn.__qualname__}", dict(ctx),
                           duration_ms=ms,
                           tag=tag if is_slow else None, caller=path)
                return rv
            return wrapper
        return deco

    # ---- 内部实现 ----
    def _should_emit(self, level: int) -> bool:
        """级别过滤 + DEBUG 采样。"""
        if level < logging.INFO:  # DEBUG
            rate = self._sample_rate
            if rate < 1.0 and random.random() >= rate:
                return False
        return True

    def _emit(self, level: int, message: str, context: dict,
              exc_info=False, duration_ms=None, tag=None, caller=None) -> None:
        if not _g_config.get("enabled", True):
            return
        if not self._should_emit(level):
            return
        if caller is not None:
            # 显式传入的业务位置 (timed/catch/log_call 使用)
            pathname, lineno, func = caller
        else:
            # 自动提取调用位置: [0]=_emit [1]=info/... [2]=业务代码
            try:
                frame = sys._getframe(2)
                pathname, lineno, func = (frame.f_code.co_filename,
                                          frame.f_lineno, frame.f_code.co_name)
            except (ValueError, AttributeError):
                pathname, lineno, func = __file__, 0, "?"
        # exc_info=True 时取当前异常栈 (LogRecord 需要元组而非 bool)
        if exc_info is True:
            exc_info = sys.exc_info()
        record = logging.LogRecord(
            name=self._name, level=level, pathname=pathname, lineno=lineno,
            msg=message, args=(), exc_info=exc_info, func=func,
        )
        record.context = dict(context or {})
        if duration_ms is not None:
            record.duration_ms = duration_ms
        if tag:
            record.tag = tag
        record.service = _g_config.get("service", SERVICE)
        record.trace_id = get_or_create_trace_id()
        # 交给标准 logging 处理器链 (file + console)
        self._logger.handle(record)


def _console_stream():
    """返回 UTF-8 编码的控制台流。

    Windows 控制台默认 GBK, 直接写中文 JSON 会 UnicodeEncodeError
    (表现为日志里的 `--- Logging error ---`), 这里重配置为 utf-8。
    """
    try:
        if sys.stderr is not None and hasattr(sys.stderr, "reconfigure"):
            sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass
    return sys.stderr


def _safe_repr(obj) -> str:
    """对象转字符串, 失败兜底 (避免 repr 本身抛异常拖垮日志)。"""
    try:
        return repr(obj)
    except Exception:
        return f"<unrepr {type(obj).__name__}>"


# 这些模块内的帧不作为业务调用位置
_EXCLUDE_FILES = ("logger.py", "contextlib.py")


def _find_caller_frame(frame):
    """从 frame 向上找到第一个业务代码帧 (跳过本模块/contextlib/logging)。"""
    f = frame
    while f is not None:
        p = f.f_code.co_filename.replace("\\", "/")
        base = os.path.basename(p)
        if (base not in _EXCLUDE_FILES
                and "/logging/" not in p
                and not p.endswith("logging/__init__.py")):
            return f
        f = f.f_back
    return frame


def _caller_info(frame):
    """从帧提取 (file, line, func) 三元组。"""
    return (frame.f_code.co_filename, frame.f_lineno, frame.f_code.co_name)


class _CtxStack:
    """线程局部操作链路上下文栈。"""

    def __init__(self):
        self.stack: list = []

    def push(self, context: dict):
        self.stack.append(dict(context))

    def pop(self):
        if self.stack:
            self.stack.pop()


# ======================================================================
# 初始化与获取
# ======================================================================

def _app_root() -> Path:
    """应用根目录 (与 config_manager.app_root 一致, 此处独立实现避免循环依赖)。"""
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parents[2]


def setup_logging(config: Optional[dict] = None,
                   root_dir: Optional[Union[str, Path]] = None):
    """初始化日志系统, 程序入口调用一次。

    Args:
        config: 日志配置 dict, 可只传部分键覆盖默认 (见 DEFAULT_CONFIG)。
                通常为 config.json 中的 "logging" 段。
        root_dir: 日志目录的基准根目录, 默认应用根目录 (exe 目录 / 项目根)。

    Returns:
        root logging.Logger (可继续 addHandler 定制)。
    """
    global _g_config
    cfg = dict(DEFAULT_CONFIG)
    if config:
        cfg.update({k: v for k, v in config.items() if v is not None})
    _g_config = cfg

    root = logging.getLogger()
    # 幂等: 每次 setup 重建 handler (防止重复初始化导致日志翻倍)
    for h in list(root.handlers):
        root.removeHandler(h)
        try:
            h.close()
        except Exception:
            pass

    level_name = str(cfg.get("level", "INFO")).upper()
    root.setLevel(getattr(logging, level_name, logging.INFO))
    fmt = JsonFormatter()

    # 1) 文件 handler (滚动)
    try:
        base = Path(root_dir) if root_dir else _app_root()
        log_dir = base / str(cfg.get("dir", "logs"))
        log_dir.mkdir(parents=True, exist_ok=True)
        fh = logging.handlers.RotatingFileHandler(
            str(log_dir / str(cfg.get("file", "app.log"))),
            maxBytes=int(cfg.get("max_bytes", DEFAULT_CONFIG["max_bytes"])),
            backupCount=int(cfg.get("backup_count", DEFAULT_CONFIG["backup_count"])),
            encoding=cfg.get("encoding", "utf-8"),
        )
        fh.setFormatter(fmt)
        fh.setLevel(root.level)
        root.addHandler(fh)
    except Exception:
        # 文件不可写时退化为仅控制台, 不阻塞启动
        fh = None

    # 2) 控制台 handler
    if cfg.get("console", True):
        ch = logging.StreamHandler(_console_stream())
        ch.setFormatter(fmt)
        ch.setLevel(root.level)
        root.addHandler(ch)

    # 刷新已创建 logger 的配置缓存
    for l in _loggers.values():
        l._slow_query_ms = cfg.get("slow", {}).get("query_ms", DEFAULT_SLOW_QUERY_MS)
        l._slow_api_ms = cfg.get("slow", {}).get("api_ms", DEFAULT_SLOW_API_MS)
        l._sample_rate = float(cfg.get("debug_sample_rate", DEFAULT_DEBUG_SAMPLE_RATE))

    return root


def get_logger(name: Optional[str] = None) -> JsonLogger:
    """获取日志器。

    Args:
        name: 业务模块名 (建议用模块名, 如 "text_polish" / "tencent_docs")。
              未传时自动取调用者模块文件名。
    """
    if name is None:
        f = sys._getframe(1)
        name = Path(f.f_code.co_filename).stem or "root"
    if name not in _loggers:
        _loggers[name] = JsonLogger(name)
    return _loggers[name]


def flush() -> None:
    """主动刷新所有 handler (程序退出前调用, 确保日志落盘)。"""
    for h in logging.getLogger().handlers:
        try:
            h.flush()
        except Exception:
            pass


def shutdown() -> None:
    """关闭日志系统 (程序退出时调用, 释放文件句柄)。"""
    flush()
    logging.shutdown()

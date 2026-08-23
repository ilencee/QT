"""
日志系统自测脚本
================
验证结构化 JSON 日志系统的核心能力, 并生成真实示例日志 (logs/smoke.log):

1. 正常操作链路 (trace_id 贯穿 + 操作链路上下文)
2. 异常场景 (ERROR + 完整堆栈 + 脱敏参数)
3. 性能场景 (SLOW_QUERY / SLOW_API 自动 WARN)
4. 自动脱敏 (密码/Token/身份证/手机号/银行卡)
5. DEBUG 采样 + 多线程 trace_id 独立性

用法: python scripts/smoke_logger.py
"""
import sys
import threading
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.core.logger import (
    setup_logging, get_logger, set_trace_id, flush,
)

CFG = {
    "dir": "logs",
    "file": "smoke.log",
    "level": "DEBUG",           # 自测时全量 DEBUG, 便于验证采样逻辑
    "console": True,
    "debug_sample_rate": 1.0,   # 自测用 1.0 保证每行都出
    "slow": {"query_ms": 10, "api_ms": 50},  # 阈值调小便于触发 SLOW
}


def demo_normal_flow():
    """场景 1: 正常操作链路 - 文本润色保存 + AI 请求"""
    log = get_logger("text_polish")
    set_trace_id()          # 操作链路起点
    log.info("开始处理润色请求", doc_type="工艺要求", chip="中微爱芯")

    with log.bind(user="alice", session="S-1001"):   # 链路上下文
        with log.timed("调用 DeepSeek 润色"):
            time.sleep(0.02)           # 模拟 AI 调用
        log.info("AI 响应已解析", chars=1280, cost_fen=3)

    log.info("模板保存成功", doc_type="工艺要求", saved=True)
    log.info("操作完成")


def demo_exception():
    """场景 2: 异常捕获 - 参数里故意带敏感信息验证脱敏"""
    log = get_logger("tencent_docs")

    def fetch_doc(token: str, url: str):
        try:
            raise ConnectionError("连接超时: 无法访问腾讯文档服务器")
        except Exception:
            log.error(
                "导入文档失败",
                context={
                    "url": url,
                    "token": token,          # 敏感键 -> 自动 ***
                    "user_phone": "13812345678",
                    "id_card": "110101199003071234",
                    "bank_card": "6222020200001234567",
                    "retry": 2,
                },
                exc_info=True,               # 自动附加完整堆栈
            )

    fetch_doc("xxx.yyy.access-token.zzz",
              "https://docs.qq.com/import?token=abc123&key=secret-key")


def demo_slow():
    """场景 3: 性能瓶颈 - 慢查询 / 慢 API 自动 WARN 打标"""
    log = get_logger("programming_software")
    with log.timed_query("扫描已安装烧录软件"):
        time.sleep(0.02)                    # 超过 query_ms=10ms -> SLOW_QUERY
    with log.timed_api("上传固件到 COS"):
        time.sleep(0.08)                    # 超过 api_ms=50ms  -> SLOW_API


def demo_debug_sampling_and_threads():
    """场景 4/5: DEBUG 采样 + 多线程 trace_id 独立"""
    log = get_logger("main")

    def worker(name: str):
        set_trace_id(f"thr-{name}")         # 每个线程独立 trace_id
        for i in range(5):
            log.debug(f"线程 {name} 处理第 {i} 项", item=i)
        log.info(f"线程 {name} 结束", items=5)

    threads = [threading.Thread(target=worker, args=(n,)) for n in ("A", "B")]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    # DEBUG 采样率 = 0.1 时应只有 ~10% 行数; 此处单独验证抽样开关
    log._sample_rate = 0.1
    hits = sum(log._should_emit(10) for _ in range(1000))
    log.info("DEBUG 采样率验证", rate=0.1, emitted=hits, expected_approx=100)
    log._sample_rate = 1.0


def demo_masking():
    """场景 6: message 文本内嵌敏感信息的脱敏"""
    log = get_logger("main")
    log.info("登录成功", account="admin@example.com")
    log.warning("请求被拒", detail='password="P@ssw0rd123" 与 api_key: sk-abcdefghijklmn 无效')
    log.info("用户注册", phone="13900001111",
             id_card="44010119920505555X")


def main():
    setup_logging(CFG)
    print("=" * 60)
    demo_normal_flow()
    demo_exception()
    demo_slow()
    demo_debug_sampling_and_threads()
    demo_masking()
    flush()
    print("=" * 60)
    log_file = Path(__file__).resolve().parents[1] / "logs" / "smoke.log"
    print(f"自测完成, 日志文件: {log_file}")


if __name__ == "__main__":
    main()

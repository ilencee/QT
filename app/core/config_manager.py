"""
配置管理器 - 管理应用程序配置
支持保存和加载串口配置等设置
"""
import json
import os
import sys
from pathlib import Path


def app_root() -> Path:
    """
    应用根目录:
    - 打包后 (PyInstaller): 返回 exe 所在目录 (config.json / assets / 外部烧录软件均放在 exe 旁边)
    - 源码运行: 返回项目根目录
    """
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parents[2]


class ConfigManager:
    """配置管理器 - 统一管理应用配置

    同 config_file 路径共享同一实例 (类级缓存):
    任一页面 (如系统设置) 修改配置并 save_config 后, 其他页面读取同一实例
    立即看到新值, 无需各自重新加载文件。
    """
    _instances: dict = {}

    def __new__(cls, config_file="config.json"):
        key = str(config_file)
        if key not in cls._instances:
            cls._instances[key] = super().__new__(cls)
        return cls._instances[key]

    def __init__(self, config_file="config.json"):
        """
        初始化配置管理器
        
        Args:
            config_file: 配置文件路径，默认为当前目录下的config.json
        """
        # 类级缓存共享: 已初始化过的实例直接复用, 不重复加载文件覆盖内存中的修改
        if getattr(self, "_initialized", False):
            self.config_file = str(config_file)
            return
        self._initialized = True
        self.config_file = str(config_file)
        self.config = self._load_config()
    
    def _load_config(self):
        """从文件加载配置"""
        if os.path.exists(self.config_file):
            try:
                with open(self.config_file, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except (json.JSONDecodeError, IOError) as e:
                print(f"加载配置文件失败: {e}，使用默认配置")
        
        # 返回默认配置
        return self._get_default_config()
    
    def _get_default_config(self):
        """获取默认配置"""
        return {
            "serial_port": {
                "port": "",
                "baudrate": 9600,
                "bytesize": 8,
                "parity": "N",
                "stopbits": 1,
                "timeout": 1,
                "auto_reconnect": False,
                "hex_display": False,
                "auto_scroll": True,
                "timestamp_display": True
            },
            "window": {
                "width": 1200,
                "height": 800,
                "theme": "Windows 11"
            },
            "general": {
                "language": "zh_CN",
                "auto_save": True,
                "log_max_lines": 10000
            },
            "power_conversion": {
                "defaults": {
                    "model_index": 0,
                    "vin": "12",
                    "current_ma": "100",
                    "derate": "80",
                    "tamb": "25",
                    "rthja": "",
                    "iq": ""
                },
                "api": {
                    "base_url": "https://api.deepseek.com/chat/completions",
                    "model": "deepseek-chat",
                    "api_key": "",
                    "temperature": 0.7,
                    "max_tokens": 1500
                },
                "regulators": {
                    "78L05 (SOT-89, 100mA)": {"vout": 5.0, "vdrop": 2.0, "rthja": 140, "imax": 100, "iq": 6},
                    "78L08 (SOT-89, 100mA)": {"vout": 8.0, "vdrop": 1.7, "rthja": 140, "imax": 100, "iq": 6},
                    "AMS1117-3.3 (SOT-223, 1A)": {"vout": 3.3, "vdrop": 1.2, "rthja": 90, "imax": 1000, "iq": 5},
                    "AMS1117-5.0 (SOT-223, 1A)": {"vout": 5.0, "vdrop": 1.2, "rthja": 90, "imax": 1000, "iq": 5},
                    "HT7533 (SOT-89, 100mA)": {"vout": 3.3, "vdrop": 0.5, "rthja": 140, "imax": 100, "iq": 0.005},
                    "HT7550 (SOT-89, 100mA)": {"vout": 5.0, "vdrop": 0.5, "rthja": 140, "imax": 100, "iq": 0.005},
                    "XC6206P332MR (SOT-23, 200mA)": {"vout": 3.3, "vdrop": 0.3, "rthja": 250, "imax": 200, "iq": 0.002},
                    "ME6211C33 (SOT-23-5, 500mA)": {"vout": 3.3, "vdrop": 0.25, "rthja": 200, "imax": 500, "iq": 0.05},
                    "LP5907MFX-3.3 (SOT-23-5, 250mA)": {"vout": 3.3, "vdrop": 0.1, "rthja": 220, "imax": 250, "iq": 0.015},
                    "RT9013-33PB (SOT-23-5, 500mA)": {"vout": 3.3, "vdrop": 0.15, "rthja": 200, "imax": 500, "iq": 0.05},
                    "MIC5205-3.3 (SOT-23-5, 150mA)": {"vout": 3.3, "vdrop": 0.2, "rthja": 220, "imax": 150, "iq": 0.11},
                    "78L05 (TO-92, 100mA)": {"vout": 5.0, "vdrop": 2.0, "rthja": 200, "imax": 100, "iq": 6},
                    "78L33 (TO-92, 100mA)": {"vout": 3.3, "vdrop": 1.7, "rthja": 200, "imax": 100, "iq": 6},
                    "7805 (TO-220, 1A)": {"vout": 5.0, "vdrop": 2.0, "rthja": 65, "imax": 1000, "iq": 8},
                    "7808 (TO-220, 1A)": {"vout": 8.0, "vdrop": 2.0, "rthja": 65, "imax": 1000, "iq": 8},
                    "7812 (TO-220, 1A)": {"vout": 12.0, "vdrop": 2.0, "rthja": 65, "imax": 1000, "iq": 8},
                    "自定义": {"vout": 5.0, "vdrop": 2.0, "rthja": 200, "imax": 100, "iq": 5}
                }
            },
            "text_polish": {
                "types": {
                    "工艺要求": {
                        "system_role": "你是一名资深电子制造工艺工程师, 擅长编写规范、严谨、可直接用于产线的工艺文件。",
                        "template": "请将用户提供的原始文本润色为规范的《工艺要求》文档, 必须严格按下述模板组织内容, 不得遗漏任何章节:\n一、适用范围\n二、作业准备\n三、工艺参数\n四、操作步骤\n五、检验要求\n六、注意事项",
                        "constraints": [
                            "必须严格按照模板章节结构输出, 不得增删、合并或调整章节顺序",
                            "每个章节必须完整展开, 条理清晰, 分条列出",
                            "术语规范, 语言专业严谨, 使用规范的中文工程用语",
                            "保留原文所有关键数据与约束, 不凭空增加内容",
                            "如原文缺少必要信息, 用【待补充】标注, 但不得省略该章节",
                            "使用 Markdown 格式输出"
                        ]
                    },
                    "测试流程": {
                        "system_role": "你是一名资深电子产品测试工程师, 擅长编写产线一线工人能直接照做的操作文档。",
                        "template": "请将用户提供的原始文本润色为规范的《测试流程》文档, 必须包含以下两个核心部分:\n一、接线说明\n二、测试步骤",
                        "constraints": [
                            "必须包含『接线说明』与『测试步骤』两大部分, 缺一不可",
                            "语言必须浅显易懂, 面向产线操作工人, 禁止使用专业术语, 无法避免时须用括号注明大白话含义",
                            "接线说明必须写明: 设备与待测板的接口位置、线序/颜色、连接方向, 不能有任何歧义",
                            "测试步骤按 1. 2. 3. 编号, 每步必须写清: 先做什么动作 → 看到什么现象 → 判定合格/不合格",
                            "判定标准必须明确具体, 不得出现『视情况而定』『大概』等模糊表述, 不得留逻辑漏洞",
                            "保留原文所有测试项、参数与判定阈值",
                            "如原文缺少必要信息, 用【待补充】标注",
                            "使用 Markdown 格式输出"
                        ]
                    },
                    "烧录指导": {
                        "constraints": [
                            "先根据原始文本明确烧录方式: 在线烧录指芯片已贴装于 PCBA, 通过 PCBA 上的烧录口手工烧录; 离线烧录指芯片未贴装, 在烧录机上对芯片本体批量烧录, 全文表述保持一致",
                            "必须写明所用烧录软件与烧录器/烧录机型号, 以及连接与操作步骤",
                            "在线烧录必须写明 PCBA 上烧录口的位置、接口类型与引脚定义 (如 VDD/GND/CLK/DAT); 离线烧录必须写明芯片烧录引脚与引脚顺序、放置方向",
                            "条理清晰, 分条列出",
                            "保留原文所有关键参数, 不凭空增加内容",
                            "如原文缺少必要信息, 用【待补充】标注",
                            "使用 Markdown 格式输出"
                        ],
                        "chips": {
                            "中微爱芯": {
                                "system_role": "你是一名资深嵌入式烧录工艺工程师, 精通中微爱芯 (AiP) 芯片的烧录, 覆盖在线烧录 (PCBA 烧录口手工烧录) 与离线烧录 (烧录机批量烧录)。",
                                "template": "请将用户提供的原始文本润色为规范的《中微爱芯 烧录指导》文档, 按以下模板组织内容:\n一、烧录工具与软件 (iWriterPro 及 AiP 烧录器)\n二、烧录口说明 (在线: PCBA 烧录口位置、接口类型与引脚定义; 离线: 芯片烧录引脚)\n三、连接方式\n四、烧录步骤\n五、校验与注意事项"
                            },
                            "十速": {
                                "system_role": "你是一名资深嵌入式烧录工艺工程师, 精通十速 (TENX) 芯片的烧录, 覆盖在线烧录 (PCBA 烧录口手工烧录) 与离线烧录 (烧录机批量烧录)。",
                                "template": "请将用户提供的原始文本润色为规范的《十速 烧录指导》文档, 按以下模板组织内容:\n一、烧录工具与软件 (TWR 系列烧录器)\n二、烧录口说明 (在线: PCBA 烧录口位置、接口类型与引脚定义; 离线: 芯片烧录引脚)\n三、连接方式\n四、烧录步骤\n五、校验与注意事项\n注意事项中必须提醒: 十速多为 OTP 芯片, 烧录前须核对型号与固件, 烧录后不可修改"
                            },
                            "兆易创新": {
                                "system_role": "你是一名资深嵌入式烧录工艺工程师, 精通兆易创新 (GigaDevice) GD32 系列芯片的烧录, 覆盖在线烧录 (SWD 接口) 与离线烧录 (烧录机批量烧录)。",
                                "template": "请将用户提供的原始文本润色为规范的《兆易创新 烧录指导》文档, 按以下模板组织内容:\n一、烧录工具与软件 (GD32 All-In-One Programmer / GD-Link Utility)\n二、烧录口说明 (在线: PCBA 上 SWD 口 SWDIO/SWCLK/GND 引脚定义; 离线: 芯片烧录引脚)\n三、连接方式\n四、烧录步骤\n五、校验与注意事项"
                            },
                            "赛元": {
                                "system_role": "你是一名资深嵌入式烧录工艺工程师, 精通赛元 (SOC) 芯片的烧录, 覆盖在线烧录 (PCBA 烧录口手工烧录) 与离线烧录 (烧录机批量烧录)。",
                                "template": "请将用户提供的原始文本润色为规范的《赛元 烧录指导》文档, 按以下模板组织内容:\n一、烧录工具与软件 (SOC Programming Tool + SC-LINK, 支持脱机烧录)\n二、烧录口说明 (在线: PCBA 烧录口位置、接口类型与引脚定义; 离线: 芯片烧录引脚)\n三、连接方式\n四、烧录步骤\n五、校验与注意事项"
                            },
                            "瑞萨": {
                                "system_role": "你是一名资深嵌入式烧录工艺工程师, 精通瑞萨 (Renesas) RA/RX/RL78 系列芯片的烧录, 覆盖在线烧录 (PCBA 烧录口手工烧录) 与离线烧录 (烧录机批量烧录)。",
                                "template": "请将用户提供的原始文本润色为规范的《瑞萨 烧录指导》文档, 按以下模板组织内容:\n一、烧录工具与软件 (Renesas Flash Programmer + E2/E2 Lite)\n二、烧录口说明 (在线: PCBA 烧录口位置与接口类型, RA 用 SWD、RL78 用单线 UART、RX 用 FINE/JTAG; 离线: 芯片烧录引脚)\n三、连接方式\n四、烧录步骤\n五、校验与注意事项"
                            }
                        }
                    }
                }
            },
            "programming_software": {
                "chips": {
                    "中微爱芯": {
                        "programmers": [
                            {
                                "name": "iWriterPro (AiP 烧录器)",
                                "exe": "烧录软件/中微爱芯/iWriterPro V1.3.09 build04273/iWriterPro.exe",
                                "desc": "中微爱芯 (AiP) 官方烧录软件, 配合 AiP 烧录器使用, 支持芯片本体烧录与 PCBA 在线烧录 (ICP)。",
                                "hardware": "AiP 烧录器 (USB 连接电脑)",
                                "usage": "1. 安装 iWriterPro 并连接烧录器\n2. 选择芯片型号, 加载固件文件\n3. 按烧录器说明放置芯片或连接 PCBA 烧录口\n4. 点击烧录, 观察状态提示, 烧录完成后核对校验结果",
                                "note": "在线烧录需确认 PCBA 烧录口引脚定义; 离线烧录需核对芯片引脚方向。",
                                "website": "http://www.i-core.cn/download.html",
                                "image": "assets/programmers/aip_iwriterpro.jpg",
                                "search_keywords": ["iWriterPro", "iWriter", "AiP"]
                            },
                            {
                                "name": "iWriterGang-4 (AiP 并口烧录器)",
                                "exe": "烧录软件/中微爱芯/iWriterGang-4_V2.0.24_build011/iWriterPro.exe",
                                "desc": "中微爱芯 iWriterGang-4 编程器配套软件, 用于 AiP 芯片并口批量烧录。",
                                "hardware": "iWriterGang-4 编程器 (并口/USB 连接电脑)",
                                "usage": "1. 安装驱动并连接 Gang-4 编程器\n2. 选择芯片型号, 加载固件文件\n3. 放入芯片到烧录座\n4. 执行批量烧录并校验",
                                "note": "Gang-4 支持一拖多批量烧录; 烧录前核对芯片型号与固件。",
                                "website": "http://www.i-core.cn/download.html",
                                "image": "assets/programmers/aip_iwritergang4.jpg",
                                "search_keywords": ["iWriterGang", "iWriter", "AiP"]
                            },
                            {
                                "name": "i_WRITER V4 (AiP 烧录软件)",
                                "exe": "烧录软件/中微爱芯/i_WRITER_V4.1.00 build001/i_WRITER.exe",
                                "desc": "中微爱芯新一代 i_WRITER V4 烧录软件, 支持 AiP 芯片烧录。",
                                "hardware": "AiP 烧录器 (USB 连接电脑)",
                                "usage": "1. 启动 i_WRITER 并连接烧录器\n2. 选择芯片型号, 加载固件文件\n3. 按烧录器说明放置芯片或连接 PCBA 烧录口\n4. 执行烧录并核对校验结果",
                                "note": "V4 版本较 iWriterPro 界面与型号库有更新, 以官方说明为准。",
                                "website": "http://www.i-core.cn/download.html",
                                "image": "assets/programmers/aip_iwriterpro.jpg",
                                "search_keywords": ["i_WRITER", "iWriter", "AiP"]
                            }
                        ]
                    },
                    "十速": {
                        "programmers": [
                            {
                                "name": "TWR98 / TWR99 / TWR100 / TWR200 烧录器",
                                "exe": "",
                                "desc": "十速 (TENX) 官方烧录器及配套软件, TWR200 支持 TM52 系列在线仿真与烧录; 海速芯/十速系列芯片通用。",
                                "hardware": "TWR98 / TWR99 / TWR100 / TWR200 烧录器",
                                "usage": "1. 连接烧录器与电脑, 安装配套驱动与软件\n2. 选择芯片型号 (如 TM57/TM58/TM52 系列), 加载固件\n3. 放置芯片到烧录座或连接 PCBA 烧录口\n4. 执行烧录并校验",
                                "note": "十速多为 OTP 芯片, 只能烧录一次, 烧录前务必核对型号与固件。",
                                "website": "https://www.hitenx.com.cn",
                                "image": "assets/programmers/twr200.jpg",
                                "search_keywords": ["TWR200", "TWR98", "TWR99", "TWR100", "TENX", "Writer"]
                            }
                        ]
                    },
                    "兆易创新": {
                        "programmers": [
                            {
                                "name": "XW16Pro Standalone Programmer",
                                "exe": "烧录软件/XW16Pro_StandaloneProgrammer/编程器软件(主软件,此包内文件均有用,若要拖出,需全拖出放同一文件夹内)/XW16ProStandaloneProgrammer.exe",
                                "desc": "XW16Pro Standalone Programmer 配合 XW16Pro 独立编程器, 用于 GD32 系列芯片的量产脱机批量烧录。",
                                "hardware": "XW16Pro 独立编程器 (USB 连接电脑)",
                                "usage": "1. 连接 XW16Pro 编程器与电脑, 启动本软件\n2. 选择芯片型号, 加载固件文件\n3. 放入芯片或连接 PCBA 的 SWD 接口 (SWDIO/SWCLK/GND)\n4. 执行烧录并校验",
                                "note": "用于量产脱机烧录; 接线与引脚定义以厂家说明书为准。",
                                "website": "http://www.xwopen.com/WpfStandaloneProgrammer.html",
                                "image": "assets/programmers/xw16pro.jpg",
                                "search_keywords": ["XW16Pro", "XW16", "StandaloneProgrammer"]
                            },
                            {
                                "name": "FT200",
                                "exe": "",
                                "desc": "FT200 烧录器 (USB 连接电脑), 可用于 GD32 系列芯片在线烧录, 具体型号选择与接线以厂家说明书为准。",
                                "hardware": "FT200 烧录器 (USB 连接电脑)",
                                "usage": "1. 安装 FT200 驱动与软件, 连接烧录器到电脑\n2. 选择 GD32 芯片型号, 加载固件\n3. 连接 PCBA 烧录口\n4. 执行烧录并校验",
                                "note": "接线与引脚定义以 FT200 厂家说明书为准。",
                                "website": "",
                                "image": "assets/programmers/ft200.png",
                                "search_keywords": ["FT200"]
                            },
                            {
                                "name": "GD32 All-In-One Programmer / GD-Link Utility",
                                "exe": "",
                                "desc": "GD32 All-In-One Programmer 支持串口 ISP、USB、CAN 等接口在线烧录; GD-Link Utility 配合 GD-Link 调试器使用。",
                                "hardware": "GD-Link / DAP-Link / J-Link / USB 转串口",
                                "usage": "1. 安装烧录软件并连接烧录器/调试器\n2. 选择接口与芯片型号, 加载固件\n3. 连接 PCBA 的 SWD 接口 (SWDIO/SWCLK/GND)\n4. 执行烧录并校验",
                                "note": "在线烧录多用 SWD 接口, 需确认 PCBA 上 SWD 接口定义。",
                                "website": "https://www.gd32mcu.com/cn/download",
                                "search_keywords": ["GD32", "GD-Link", "GDLink", "All-In-One"]
                            }
                        ]
                    },
                    "赛元": {
                        "programmers": [
                            {
                                "name": "SOC Programming Tool (SC-LINK / SC-LINK PRO)",
                                "exe": "烧录软件/赛元/SOC Programming Tool Enhance v1.80(LIB1D00)/SOC Programming Tool Enhance v1.80(LIB1D00).exe",
                                "desc": "赛元 (SOC) 官方全功能烧录软件, 同时配合 SC-LINK 与 SC-LINK PRO 两款烧录器使用, 支持编程、校验、查空、在线/脱机/自动烧录、加密、序列号、烧录电压选择及两款烧录器固件升级。",
                                "hardware": "SC-LINK 与 SC-LINK PRO 两款烧录器通用 (两款固件不通用)",
                                "usage": "1. 安装 SOC Programming Tool 并连接 SC-LINK 或 SC-LINK PRO\n2. 选择芯片型号, 加载固件\n3. 若未找到芯片型号或无法仿真, 点击「升级」更新 MCU 库或烧录器固件\n4. 连接 PCBA 烧录口或放置芯片到烧录座, 执行编程、校验, 可配置脱机烧录",
                                "note": "SC-LINK 与 SC-LINK PRO 是两款不同烧录器, 共用本软件但固件不一致不可互换: SC-LINK 使用 V2.x / V3.40 固件 (V2.x 配套资料含 SOC PRO51); SC-LINK PRO 使用 51版 / ARM版 固件。连接后需确保烧录器固件与所用芯片匹配。",
                                "website": "https://socmcu.com/cn/tool_show.php?id=43",
                                "image": ["assets/programmers/sc_link.png", "assets/programmers/sc_link_pro.png"],
                                "search_keywords": ["SOC Programming Tool", "SOC", "SC-LINK"]
                            },
                            {
                                "name": "SOC Pro51 (SC51F 系列烧录软件)",
                                "exe": "烧录软件/赛元/SOC+Pro51/SOC Pro51 v5.20.exe",
                                "desc": "赛元 SOC Pro51 烧录软件, 用于 SC51F 等 8051 内核芯片烧录, 配合 SC-LINK (V2.x 固件) 使用。",
                                "hardware": "SC-LINK 烧录器 (V2.x 版本固件)",
                                "usage": "1. 启动 SOC Pro51 并连接 SC-LINK (V2.x 固件)\n2. 选择 SC51F 芯片型号, 加载固件文件\n3. 按烧录器说明放置芯片或连接 PCBA 烧录口\n4. 执行烧录并核对校验结果",
                                "note": "SOC Pro51 配合 SC-LINK (V2.x 版本固件) 使用, 不建议连接 SC-LINK PRO。SC51F 新项目推荐使用 SOC Programming Tool 配合 SC-LINK (V2.x 固件) 烧录。",
                                "website": "https://socmcu.com/cn/tool_show.php?id=43",
                                "image": "assets/programmers/sc_link.png",
                                "search_keywords": ["SOC Pro51", "SOC", "Pro51"]
                            }
                        ]
                    },
                    "瑞萨": {
                        "programmers": [
                            {
                                "name": "Renesas Flash Programmer (RFP)",
                                "exe": "",
                                "desc": "瑞萨 (Renesas) 官方闪存烧录软件 (RFP), 支持 RA / RX / RL78 系列 MCU 片上 Flash 编程, 需搭配 E1/E2/E2 Lite/E20 仿真调试器使用。",
                                "hardware": "E1 / E2 / E2 Lite / E20 仿真调试器 (或板载调试器)",
                                "usage": "1. 安装 Renesas Flash Programmer 并连接 E2/E2 Lite 调试器\n2. 选择 MCU 型号与调试接口 (RA 用 SWD, RL78 用单线 UART, RX 用 FINE/JTAG)\n3. 加载烧录文件 (hex/mot/bin)\n4. 执行擦除、写入、校验",
                                "note": "RFP 免费版可用于评估; 量产烧录建议向瑞萨或授权代理商咨询授权方案。",
                                "website": "https://www.renesas.cn/zh/software-tool/renesas-flash-programmer-programming-gui",
                                "image": [
                                    "assets/programmers/renesas_e2.png",
                                    "assets/programmers/renesas_e2lite.png",
                                    "assets/programmers/renesas_e1.jpg",
                                    "assets/programmers/renesas_e20.jpg"
                                ],
                                "search_keywords": ["Renesas Flash Programmer", "RFP", "Renesas"]
                            }
                        ]
                    }
                }
            }
        }
    
    def get_factory_defaults(self):
        """获取出厂默认配置 (用于恢复默认)"""
        return self._get_default_config()
    
    def save_config(self):
        """保存配置到文件"""
        try:
            with open(self.config_file, 'w', encoding='utf-8') as f:
                json.dump(self.config, f, indent=4, ensure_ascii=False)
            return True
        except IOError as e:
            print(f"保存配置文件失败: {e}")
            return False
    
    # ==================== 串口配置相关方法 ====================
    def get_serial_config(self):
        """获取串口配置"""
        return self.config.get("serial_port", {})
    
    def _serial_section(self) -> dict:
        """返回串口配置段, 缺失时自动创建 (防止 config.json 缺段导致 KeyError)"""
        return self.config.setdefault("serial_port", {})

    def set_serial_port(self, port):
        """设置串口号"""
        self._serial_section()["port"] = port
    
    def set_baudrate(self, baudrate):
        """设置波特率"""
        self._serial_section()["baudrate"] = baudrate
    
    def set_bytesize(self, bytesize):
        """设置数据位"""
        self._serial_section()["bytesize"] = bytesize
    
    def set_parity(self, parity):
        """设置校验位"""
        self._serial_section()["parity"] = parity
    
    def set_stopbits(self, stopbits):
        """设置停止位"""
        self._serial_section()["stopbits"] = stopbits
    
    def set_timeout(self, timeout):
        """设置超时时间"""
        self._serial_section()["timeout"] = timeout
    
    def set_auto_reconnect(self, auto_reconnect):
        """设置自动重连"""
        self._serial_section()["auto_reconnect"] = auto_reconnect
    
    def set_hex_display(self, hex_display):
        """设置十六进制显示"""
        self._serial_section()["hex_display"] = hex_display
    
    def set_auto_scroll(self, auto_scroll):
        """设置自动滚动"""
        self._serial_section()["auto_scroll"] = auto_scroll
    
    def set_timestamp_display(self, timestamp_display):
        """设置时间戳显示"""
        self._serial_section()["timestamp_display"] = timestamp_display
    
    def get_full_serial_params(self):
        """获取完整的串口参数字典"""
        params = self.config.get("serial_port", {})
        return {
            "port": params.get("port", ""),
            "baudrate": params.get("baudrate", 9600),
            "bytesize": params.get("bytesize", 8),
            "parity": params.get("parity", "N"),
            "stopbits": params.get("stopbits", 1),
            "timeout": params.get("timeout", 1)
        }
    
    # ==================== 窗口配置相关方法 ====================
    def get_window_config(self):
        """获取窗口配置"""
        return self.config.get("window", {})
    
    def set_window_size(self, width, height):
        """设置窗口大小"""
        self.config["window"]["width"] = width
        self.config["window"]["height"] = height
    
    def set_theme(self, theme):
        """设置主题"""
        self.config["window"]["theme"] = theme
    
    # ==================== 通用配置相关方法 ====================
    def get_general_config(self):
        """获取通用配置"""
        return self.config.get("general", {})
    
    def set_language(self, language):
        """设置语言"""
        self.config["general"]["language"] = language
    
    def set_auto_save(self, auto_save):
        """设置自动保存"""
        self.config["general"]["auto_save"] = auto_save
    
    def set_log_max_lines(self, max_lines):
        """设置日志最大行数"""
        self.config["general"]["log_max_lines"] = max_lines
    
    # ==================== 通用方法 ====================
    def get_value(self, key_path, default=None):
        """
        通过路径获取配置值
        
        Args:
            key_path: 键路径，如 "serial_port.baudrate"
            default: 默认值
            
        Returns:
            配置值或默认值
        """
        keys = key_path.split(".")
        value = self.config
        
        for key in keys:
            if isinstance(value, dict) and key in value:
                value = value[key]
            else:
                return default
        
        return value
    
    def set_value(self, key_path, value):
        """
        通过路径设置配置值
        
        Args:
            key_path: 键路径，如 "serial_port.baudrate"
            value: 要设置的值
        """
        keys = key_path.split(".")
        config = self.config
        
        for key in keys[:-1]:
            if key not in config:
                config[key] = {}
            config = config[key]
        
        config[keys[-1]] = value
    
    def reset_to_default(self):
        """重置为默认配置"""
        self.config = self._get_default_config()
        self.save_config()

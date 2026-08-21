"""
配置管理器 - 管理应用程序配置
支持保存和加载串口配置等设置
"""
import json
import os
from pathlib import Path


class ConfigManager:
    """配置管理器 - 统一管理应用配置"""
    
    def __init__(self, config_file="config.json"):
        """
        初始化配置管理器
        
        Args:
            config_file: 配置文件路径，默认为当前目录下的config.json
        """
        self.config_file = config_file
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
    
    def set_serial_port(self, port):
        """设置串口号"""
        self.config["serial_port"]["port"] = port
    
    def set_baudrate(self, baudrate):
        """设置波特率"""
        self.config["serial_port"]["baudrate"] = baudrate
    
    def set_bytesize(self, bytesize):
        """设置数据位"""
        self.config["serial_port"]["bytesize"] = bytesize
    
    def set_parity(self, parity):
        """设置校验位"""
        self.config["serial_port"]["parity"] = parity
    
    def set_stopbits(self, stopbits):
        """设置停止位"""
        self.config["serial_port"]["stopbits"] = stopbits
    
    def set_timeout(self, timeout):
        """设置超时时间"""
        self.config["serial_port"]["timeout"] = timeout
    
    def set_auto_reconnect(self, auto_reconnect):
        """设置自动重连"""
        self.config["serial_port"]["auto_reconnect"] = auto_reconnect
    
    def set_hex_display(self, hex_display):
        """设置十六进制显示"""
        self.config["serial_port"]["hex_display"] = hex_display
    
    def set_auto_scroll(self, auto_scroll):
        """设置自动滚动"""
        self.config["serial_port"]["auto_scroll"] = auto_scroll
    
    def set_timestamp_display(self, timestamp_display):
        """设置时间戳显示"""
        self.config["serial_port"]["timestamp_display"] = timestamp_display
    
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

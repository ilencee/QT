"""
工作助手 - 统一入口

启动方式:
    python main.py

架构:
    app/
    ├── main_window.py   主窗口 (导航 + 页面切换)
    ├── pages/           功能页面
    ├── core/            核心模块 (配置/样式)
    └── tools/           独立工具
"""

from app.main_window import main

if __name__ == "__main__":
    main()

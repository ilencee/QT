from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QPushButton, QFrame, QSplitter, QTextEdit, QMessageBox, QFileDialog, QMenuBar, QMenu, QScrollArea, QGridLayout, QStackedWidget, QComboBox
)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QFont, QIcon, QGuiApplication
import sys
import os
import importlib
from app.core.config_manager import app_root, ConfigManager
from app.core.theme import (apply_theme, system_font, ACCENT, TEXT,
                            TEXT_SECONDARY, BORDER, BG)

# 页面模块延迟导入: 不在顶部 import, 由 _page_factory 在首次切换页面时才加载,
# 避免 text_polish/settings 等页面连带 import 的 AI 客户端 / 腾讯文档 SDK 阻塞启动


def _page_factory(module_name, class_name, **kwargs):
    """延迟导入页面模块并返回创建函数（首次切换页面时才加载，避免启动阻塞）。

    统一走 importlib 避免 lambda 闭包陷阱；kwargs 固定为创建页面时的参数。
    """
    def _create():
        module = importlib.import_module(module_name)
        cls = getattr(module, class_name)
        return cls(**kwargs)
    return _create


class SerialDebugTool(QMainWindow):
    def __init__(self):
        super().__init__()
        self.initUI()
        # 不在此处 show(): 窗口显示与构造分离, 由 main() 显式控制

    def initUI(self):
        # 设置窗口基本属性
        self.setWindowTitle('工作助手')
        icon_path = str(app_root() / "assets" / "icon.png")
        if os.path.exists(icon_path):
            self.setWindowIcon(QIcon(icon_path))
        # 记忆窗口位置/大小: 从 config.json 恢复上次状态, 无记录时用默认 1200x800
        self._cfg = ConfigManager(str(app_root() / "config.json"))
        wcfg = self._cfg.get_window_config()
        try:
            wx = int(wcfg.get("x", 100))
            wy = int(wcfg.get("y", 100))
            ww = max(int(wcfg.get("width", 1200)), 800)
            wh = max(int(wcfg.get("height", 800)), 600)
        except (TypeError, ValueError):
            wx, wy, ww, wh = 100, 100, 1200, 800
        # 窗口尺寸/位置限制在屏幕可用区域内 (换屏或分辨率变化后防止窗口
        # 超出屏幕导致过高/无法拖拽调整; 高度取两者较小值, 保证可调大小)
        screen = QGuiApplication.primaryScreen()
        if screen is not None:
            avail = screen.availableGeometry()
            ww = min(ww, avail.width())
            wh = min(wh, avail.height())
            wx = max(avail.left(), min(wx, avail.right() - ww + 1))
            wy = max(avail.top(), min(wy, avail.bottom() - wh + 1))
        self.setGeometry(wx, wy, ww, wh)

        # 记录导航栏状态
        self.nav_expanded = bool(wcfg.get("nav_expanded", True))  # True=展开, False=收起
        
        # 创建中央部件
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        
        # 主布局
        main_layout = QHBoxLayout(central_widget)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)
        
        # ===== 左侧导航栏 =====
        nav_frame = QFrame()
        nav_frame.setObjectName("navFrame")
        nav_frame.setFixedWidth(200)
        self.nav_frame = nav_frame  # 保存引用以便后续修改宽度
        nav_layout = QVBoxLayout(nav_frame)
        nav_layout.setContentsMargins(10, 20, 10, 20)
        nav_layout.setSpacing(5)
        
        # 标题栏(带切换按钮)
        title_layout = QHBoxLayout()
        
        self.title_label = QLabel("⚡ 工作助手")
        _title_font = system_font(16)
        _title_font.setBold(True)
        self.title_label.setFont(_title_font)
        self.title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.title_label.setStyleSheet(f"color: {TEXT}; padding: 10px; letter-spacing: 1px;")
        title_layout.addWidget(self.title_label)
        
        # 切换按钮
        toggle_btn = QPushButton("◀")
        toggle_btn.setFixedSize(30, 30)
        toggle_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        toggle_btn.setStyleSheet(f"""
            QPushButton {{
                background: transparent;
                color: {TEXT_SECONDARY};
                border: none;
                border-radius: 15px;
                font-size: 14px;
            }}
            QPushButton:hover {{
                background: rgba(0, 122, 255, 0.12);
                color: {ACCENT};
            }}
        """)
        toggle_btn.clicked.connect(self.toggle_nav_bar)
        self.toggle_btn = toggle_btn  # 保存引用, 避免通过布局索引反查
        title_layout.addWidget(toggle_btn)
        
        nav_layout.addLayout(title_layout)
        
        nav_layout.addSpacing(20)
        
        # 保存导航项数据
        self.nav_items = [
            ("🏠", "首页概览"),
            ("🔌", "串口调试"),
            ("📄", "文本润色"),
            ("💾", "烧录软件"),
            ("🔧", "硬件工具箱"),
            ("📚", "常识查询"),
            ("⚙️", "系统设置")
        ]
        
        # 导航按钮列表
        self.nav_buttons = []
        for index, (icon, text) in enumerate(self.nav_items):
            btn = self.create_nav_button(icon, text, index)
            nav_layout.addWidget(btn)
            self.nav_buttons.append(btn)
        
        nav_layout.addStretch()
        
        # ===== 右侧内容区 - 使用堆叠窗口 =====
        content_widget = QWidget()
        content_layout = QVBoxLayout(content_widget)
        content_layout.setContentsMargins(20, 20, 20, 20)
        content_layout.setSpacing(20)
        
        # 堆叠窗口 - 用于切换不同页面
        self.stacked_widget = QStackedWidget()
        
        # 页面工厂 (延迟导入: 首次切换页面时才 import 对应模块,
        # 避免 text_polish/settings 等页面连带加载的 AI 客户端 / 腾讯文档 SDK 阻塞启动)
        self._page_factories = [
            _page_factory("app.pages.home_page", "HomePage", on_navigate=self.switch_page),
            _page_factory("app.pages.serial_debug_page", "SerialDebugPage"),
            _page_factory("app.pages.text_polish_page", "TextPolishPage"),
            _page_factory("app.pages.programming_software_page", "ProgrammingSoftwarePage"),
            _page_factory("app.pages.hardware_toolbox_page", "HardwareToolboxPage"),
            _page_factory("app.pages.reference_lookup_page", "ReferenceLookupPage"),
            _page_factory("app.pages.settings_page", "SettingsPage",
                          on_visibility_changed=self._apply_page_visibility,
                          nav_items=self.nav_items),
        ]
        self._pages: dict = {}

        # 启动时只创建默认页 (首页)
        self._ensure_page(0)
        
        content_layout.addWidget(self.stacked_widget)
        
        # 添加到主布局
        main_layout.addWidget(nav_frame)
        main_layout.addWidget(content_widget, 1)
        
        # 默认选中首页
        self.nav_buttons[0].setChecked(True)
        
        # 应用样式
        self.apply_styles()

        # 恢复导航栏收起状态 (直接应用, 不翻转状态)
        self._apply_nav_state(self.nav_expanded)

        # 导航栏右键菜单: 快速隐藏/显示栏目
        self.nav_frame.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.nav_frame.customContextMenuRequested.connect(self._show_nav_context_menu)

        # 读取并应用栏目隐藏配置 (首页/系统设置锁定恒可见, 其余按需隐藏)
        self._hidden_pages = set(self._cfg.get_window_config().get("hidden_pages", []) or [])
        self._apply_page_visibility(self._hidden_pages)
    
    def create_nav_button(self, icon, text, index):
        """创建导航按钮 (macOS 侧边栏风格: hover 浅灰胶囊, 选中 accent 浅蓝底 + 左侧指示条)"""
        btn = QPushButton(f"{icon}  {text}")
        btn.setMinimumHeight(44)
        btn.setFont(system_font(11))
        btn.setCursor(Qt.CursorShape.PointingHandCursor)
        btn.setProperty("index", index)  # 保存页面索引
        btn.setStyleSheet(f"""
            QPushButton {{
                background: transparent;
                color: {TEXT};
                border: none;
                border-left: 3px solid transparent;
                border-radius: 10px;
                text-align: left;
                padding-left: 12px;
                padding-right: 12px;
            }}
            QPushButton:hover {{
                background: rgba(0, 0, 0, 0.05);
                color: {TEXT};
            }}
            QPushButton:checked {{
                background: rgba(0, 122, 255, 0.10);
                color: {ACCENT};
                border-left: 3px solid {ACCENT};
                font-weight: bold;
            }}
        """)
        btn.setCheckable(True)
        btn.clicked.connect(lambda: self.switch_page(index))
        return btn
    
    def switch_page(self, index):
        """切换页面"""
        # 切走前让当前页面处理未保存的修改 (如文本润色页模板编辑区的手工保存确认);
        # 用户选择「取消」时中止切换
        if not self._flush_all_pages():
            return
        # 取消其他按钮的选中状态
        for i, btn in enumerate(self.nav_buttons):
            if i != index:
                btn.setChecked(False)
        
        # 懒加载: 首次访问才创建页面, 按对象切换 (不依赖堆叠索引, 避免错位)
        page = self._ensure_page(index)
        self.stacked_widget.setCurrentWidget(page)

    def _flush_all_pages(self) -> bool:
        """当前页面有未保存修改时让其确认 (模板手工保存场景)。
        返回 False 表示用户取消, 调用方应中止切换/关闭。"""
        cur = self.stacked_widget.currentWidget()
        if cur is not None and hasattr(cur, "flush_pending_save"):
            try:
                return cur.flush_pending_save() is not False
            except Exception:
                pass
        return True
    
    def _ensure_page(self, index):
        """按需创建页面 (懒加载)"""
        if index not in self._pages:
            self._pages[index] = self._page_factories[index]()
            self.stacked_widget.addWidget(self._pages[index])
        return self._pages[index]

    # ==================== 栏目显隐 ====================
    def _apply_page_visibility(self, hidden):
        """统一应用栏目显隐: 导航按钮可见性 + 首页卡片同步 + 当前页被隐藏时自动切换。

        首页(0)/系统设置(6) 为锁定栏目, 恒可见 (防止失去管理入口)。
        """
        hidden = set(hidden or [])
        locked = {self.nav_items[0][1], self.nav_items[-1][1]}  # 首页概览 / 系统设置
        hidden -= locked
        self._hidden_pages = hidden

        for btn, (_, name) in zip(self.nav_buttons, self.nav_items):
            btn.setVisible(name not in hidden)

        # 首页快捷卡片同步
        home = self._pages.get(0)
        if home is not None and hasattr(home, "set_hidden_pages"):
            home.set_hidden_pages(hidden)

        # 当前页被隐藏时自动切到第一个可见栏目 (手动切换, 不触发未保存确认打断)
        cur = self.stacked_widget.currentWidget()
        if cur is None:
            return
        cur_index = next((i for i, p in self._pages.items() if p is cur), None)
        if cur_index is None or self.nav_items[cur_index][1] not in hidden:
            return
        for target, (_, name) in enumerate(self.nav_items):
            if name not in hidden:
                for i, btn in enumerate(self.nav_buttons):
                    btn.setChecked(i == target)
                page = self._ensure_page(target)
                self.stacked_widget.setCurrentWidget(page)
                return

    def _show_nav_context_menu(self, pos):
        """导航栏右键菜单: 勾选/取消快速切换栏目显示状态"""
        menu = QMenu(self)
        menu.setStyleSheet("font-size: 13px;")
        header = QLabel("显示 / 隐藏栏目")
        header.setStyleSheet(
            f"color: {TEXT_SECONDARY}; padding: 6px 22px; font-weight: bold;")
        header.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        # 以 QWidgetAction 方式添加标题 (QLabel 作为菜单首项)
        from PyQt6.QtWidgets import QWidgetAction
        wact = QWidgetAction(menu)
        wact.setDefaultWidget(header)
        menu.addAction(wact)
        menu.addSeparator()

        for index, (icon, name) in enumerate(self.nav_items):
            item = menu.addAction(f"{icon}  {name}")
            item.setCheckable(True)
            item.setChecked(name not in self._hidden_pages)
            if index in (0, len(self.nav_items) - 1):
                # 锁定栏目: 固定显示, 菜单中禁用
                item.setEnabled(False)
                item.setToolTip("固定栏目，不可隐藏")
            else:
                item.toggled.connect(
                    lambda checked, idx=index, nm=name: self._on_nav_menu_toggled(idx, nm, checked))
        menu.exec(self.nav_frame.mapToGlobal(pos))

    def _on_nav_menu_toggled(self, index, name, checked):
        """右键菜单勾选变化: 更新 hidden 列表并写配置、应用显隐"""
        hidden = set(self._hidden_pages)
        if checked:
            hidden.discard(name)
        else:
            hidden.add(name)
        self._hidden_pages = hidden
        try:
            self._cfg.set_value("window.hidden_pages", sorted(hidden))
            self._cfg.save_config()
        except Exception:
            pass
        self._apply_page_visibility(hidden)

    def toggle_nav_bar(self):
        """切换导航栏展开/收起状态"""
        self._apply_nav_state(not self.nav_expanded)

    def _apply_nav_state(self, expanded: bool):
        """按状态应用导航栏外观 (展开/收起), 不翻转状态"""
        self.nav_expanded = expanded

        if expanded:
            # 展开模式
            self.nav_frame.setFixedWidth(200)
            self.title_label.setText("⚡ 工作助手")
            self.toggle_btn.setText("◀")

            # 更新按钮显示文字
            for btn, (icon, text) in zip(self.nav_buttons, self.nav_items):
                btn.setText(f"{icon}  {text}")
        else:
            # 收起模式(只显示图标)
            self.nav_frame.setFixedWidth(70)
            self.title_label.setText("⚡")
            self.toggle_btn.setText("▶")

            # 更新按钮只显示图标
            for btn, (icon, text) in zip(self.nav_buttons, self.nav_items):
                btn.setText(f"{icon}")
    
    def create_card(self, title, value, icon, color):
        """创建信息卡片"""
        card = QFrame()
        card.setObjectName("card")
        card.setFixedHeight(120)
        card.setStyleSheet(f"""
            QFrame#card {{
                background: white;
                border-radius: 8px;
                border-left: 4px solid {color};
            }}
            QFrame#card:hover {{
                background: #F5F7FA;
            }}
        """)
        
        layout = QVBoxLayout(card)
        layout.setContentsMargins(20, 15, 20, 15)
        layout.setSpacing(8)
        
        # 图标和标题行
        top_layout = QHBoxLayout()
        icon_label = QLabel(icon)
        icon_label.setFont(QFont("Microsoft YaHei", 20))
        top_layout.addWidget(icon_label)
        
        title_label = QLabel(title)
        title_label.setFont(QFont("Microsoft YaHei", 12))
        title_label.setStyleSheet("color: #666;")
        top_layout.addWidget(title_label)
        top_layout.addStretch()
        layout.addLayout(top_layout)
        
        # 数值
        value_label = QLabel(value)
        value_label.setFont(QFont("Microsoft YaHei", 18, QFont.Weight.Bold))
        value_label.setStyleSheet(f"color: {color};")
        layout.addWidget(value_label)
        
        return card
    
    def apply_styles(self):
        """应用窗口级样式 (macOS 风格; 全局主题由 main() 中 apply_theme 统一负责)"""
        self.setStyleSheet(f"""
            QMainWindow {{
                background: {BG};
            }}
            QFrame#navFrame {{
                background: white;
                border-right: 1px solid {BORDER};
            }}
            QFrame#card {{
                background: white;
                border-radius: 14px;
                border: 1px solid {BORDER};
            }}
        """)

    def _save_window_state(self):
        """记忆窗口位置/大小与导航栏展开状态到 config.json (可独立测试)"""
        wcfg = self._cfg.config.setdefault("window", {})
        g = self.geometry()
        wcfg["x"] = g.x()
        wcfg["y"] = g.y()
        wcfg["width"] = g.width()
        wcfg["height"] = g.height()
        wcfg["nav_expanded"] = self.nav_expanded
        self._cfg.save_config()

    def closeEvent(self, event):
        """关闭窗口: 先处理各页面未保存的修改 (取消则不关闭), 再记忆窗口位置/大小等"""
        try:
            if not self._flush_all_pages():
                event.ignore()  # 用户取消: 不关闭窗口
                return
            self._save_window_state()
        except Exception:
            pass  # 落盘/记忆失败不影响关闭
        super().closeEvent(event)


def main():
    # 初始化日志系统 (失败不阻塞启动)
    try:
        from app.core.logger import setup_logging, get_logger, flush
        cfg = ConfigManager(str(app_root() / "config.json"))
        setup_logging(cfg.config.get("logging"))
        _log = get_logger("main")
        _log.info("应用启动", version="1.0.0")
    except Exception:
        _log = None

    # Windows 任务栏图标支持 (需在创建窗口前设置)
    if os.name == "nt":
        try:
            import ctypes
            # 声明参数类型为宽字符串指针, 避免 64 位下指针截断导致设置失败
            ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID.restype = ctypes.c_long
            ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID.argtypes = [ctypes.c_wchar_p]
            ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID("SerialDebugTool.WorkAssistant")
        except Exception:
            pass

    # DPI 高分屏缩放策略: 必须在 QApplication 创建前设置,
    # 保证 Win10/Win11 在 125%/150%/200% 等非整数缩放比例下界面清晰
    if sys.platform == "win32":
        try:
            QGuiApplication.setHighDpiScaleFactorRoundingPolicy(
                Qt.HighDpiScaleFactorRoundingPolicy.PassThrough)
        except Exception:
            pass

    app = QApplication(sys.argv)

    # 全局主题: macOS 风格 QSS + 字体回退 (无微软雅黑时自动回退 Segoe UI)
    try:
        apply_theme(app)
    except Exception:
        pass

    # 系统版本温和提示 (Qt6 官方最低支持 Win10 1809, 仅提示不阻止运行)
    try:
        if sys.platform == "win32":
            ver = sys.getwindowsversion()
            if ver.major < 10 or (ver.major == 10 and ver.build < 17763):
                QMessageBox.warning(
                    None, "系统提示",
                    "当前 Windows 版本较旧（低于 Windows 10 1809）。\n"
                    "软件可能无法正常显示，建议升级至 Windows 10 1809 或 Windows 11。")
    except Exception:
        pass

    ex = SerialDebugTool()
    ex.show()
    ret = app.exec()
    if _log is not None:
        try:
            from app.core.logger import flush, shutdown
            _log.info("应用退出", exit_code=ret)
            flush()
            shutdown()
        except Exception:
            pass
    sys.exit(ret)


if __name__ == '__main__':
    main()

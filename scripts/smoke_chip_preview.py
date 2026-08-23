# -*- coding: utf-8 -*-
"""冒烟测试: 所有类型模板即润色内容 (与烧录指导一致); 芯片切换防丢; 恢复按钮; 模板插图"""
import base64
import os
import sys
import traceback

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from PyQt6.QtCore import QMimeData, QUrl
from PyQt6.QtGui import QImage
from PyQt6.QtWidgets import QApplication, QMessageBox
import app.pages.text_polish_page as m
from app.pages.text_polish_page import (
    TemplateEdit,
    TextPolishPage,
    _edit_save_text,
    _is_html_template,
    _plain_with_img_mark,
    _set_edit_content,
)

print("T1: import ok", flush=True)
app = QApplication(sys.argv)
print("T2: QApplication ok", flush=True)

# 备份 config.json, 测试结束时恢复 (避免测试输入/保存污染用户配置)
import shutil

_cfg_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "config.json")
_cfg_bak = _cfg_path + ".smoke_bak"
shutil.copy(_cfg_path, _cfg_bak)
try:
    page = TextPolishPage()
    print("T3: TextPolishPage ok", flush=True)
except Exception:
    traceback.print_exc()
    raise

def norm_edit_text():
    """编辑框纯文本与模板 HTML→纯文本 的归一化比较 (图片占位统一为 [图片])"""
    return page.template_preview_edit.toPlainText().replace("\ufffc", " [图片] ").strip()

# 初始: 工艺要求 → 模板编辑区对所有类型可见, 标题统一为"模板即润色内容", 加载该类型模板
assert not page.template_preview_frame.isHidden(), "初始模板编辑区应可见 (所有类型通用)"
assert "模板即润色内容" in page.template_card_title.text(), "初始模板卡标题应统一为模板即润色内容"
gongyi_tpl = _plain_with_img_mark(page.polish_types.get("工艺要求", {}).get("template") or "")
assert norm_edit_text() == gongyi_tpl, "非烧录模板区应加载该类型模板"

# 切到烧录指导
for btn in page.type_group.buttons():
    if btn.text() == "烧录指导":
        btn.setChecked(True)
        break
page._on_type_changed()
assert not page.chip_row_frame.isHidden(), "烧录指导时应显示芯片行"
assert not page.template_preview_frame.isHidden(), "烧录指导时模板编辑区应显示"
assert "模板即润色内容" in page.template_card_title.text(), "烧录指导模板卡标题应统一为模板即润色内容"

# 逐个芯片: 编辑框 = 该芯片模板, 可编辑
chips = list(page.polish_types["烧录指导"]["chips"].keys())
assert chips, "默认应有芯片"
for chip in chips:
    page.chip_combo.blockSignals(True)
    page.chip_combo.setCurrentText(chip)
    page.chip_combo.blockSignals(False)
    page._update_template_preview()
    cfg = page._resolve_type_cfg()
    text = page.template_preview_edit.toPlainText().strip()
    assert norm_edit_text() == _plain_with_img_mark(cfg.get("template") or ""), f"{chip} 模板未加载"
    # 直接编辑 (模拟用户修改)
    page.template_preview_edit.setPlainText(text + "\n自定义补充")
    assert page._template_dirty(), f"{chip} 修改后应判定脏"
    assert not page._loaded_template_text.endswith("自定义补充"), "loaded 不应被用户修改污染"
    # 恢复按钮
    page._restore_template()
    assert not page._template_dirty(), f"{chip} 恢复后不应脏"
    page.template_preview_edit.setPlainText(text + "\n自定义补充")  # 恢复脏状态
    page._restore_template()
    print(f"OK {chip}: {len(text)} 字")

# 清空输入适配烧录指导
page._clear_input()
assert page.template_preview_edit.toPlainText() == "", "清空应清模板编辑框"
page._restore_template()

# 芯片切换防丢: 修改后触发 _on_chip_changed; 确认返回 cancel → 回退并保留修改
orig_confirm = m.TextPolishPage._confirm_unsaved
m.TextPolishPage._confirm_unsaved = lambda self, *a, **k: "cancel"
first, second = chips[0], chips[1]
page.chip_combo.blockSignals(True)
page.chip_combo.setCurrentText(first)
page.chip_combo.blockSignals(False)
page._update_template_preview()
page._prev_chip = first
page.template_preview_edit.setPlainText(page.template_preview_edit.toPlainText() + "\nX")
assert page._template_dirty(), "修改后应判定脏"
page.chip_combo.blockSignals(True)
page.chip_combo.setCurrentText(second)
page.chip_combo.blockSignals(False)
page._on_chip_changed()
assert page.chip_combo.currentText() == first, "取消应回退原芯片"
assert page._template_dirty(), "回退后修改应保留"
# 确认返回 discard → 切换到新芯片 (不保存旧修改)
m.TextPolishPage._confirm_unsaved = lambda self, *a, **k: "discard"
page.chip_combo.blockSignals(True)
page.chip_combo.setCurrentText(second)
page.chip_combo.blockSignals(False)
page._on_chip_changed()
assert page.chip_combo.currentText() == second, "不保存也应切换到新芯片"
assert not page._template_dirty(), "切换后加载新模板不应脏"
assert norm_edit_text() == _plain_with_img_mark(page._resolve_type_cfg().get("template") or ""), "切换后编辑框应加载新芯片模板"
m.TextPolishPage._confirm_unsaved = orig_confirm

# 切回非烧录指导
for btn in page.type_group.buttons():
    if btn.text() == "工艺要求":
        btn.setChecked(True)
        break
page._on_type_changed()
assert page.chip_row_frame.isHidden(), "非烧录指导时芯片行应隐藏"
assert not page.template_preview_frame.isHidden(), "切回后模板编辑区仍应可见"
assert "模板即润色内容" in page.template_card_title.text(), "切回后标题应统一"
# 非烧录指导的模板区应加载该类型模板
gongyi_tpl = _plain_with_img_mark(page.polish_types.get("工艺要求", {}).get("template") or "")
assert norm_edit_text() == gongyi_tpl, "非烧录模板区应加载该类型模板"

# 限制要求窗口: 非烧录类型可打开并保存角色/限制 (保存不关窗)
from app.pages.text_polish_page import ConstraintsDialog
dlg = ConstraintsDialog(page.cfg, page.polish_types, "工艺要求", "", page)
assert "限制要求" in dlg.windowTitle(), "限制窗口标题错误"
dlg.show()  # offscreen 下 show 后窗口可见, 用于验证保存不关闭
# 先记录原始值快照, 恢复时用快照 (不能从已保存后的内存读, 会被污染)
orig_role = page.polish_types.get("工艺要求", {}).get("system_role", "")
orig_constraints = page.polish_types.get("工艺要求", {}).get("constraints", [])
dlg.role_edit.setText("你是工艺专家")
dlg.constraints_edit.setPlainText("限制A\n限制B\n\n限制C")
dlg._save()
assert page.polish_types["工艺要求"]["constraints"] == ["限制A", "限制B", "限制C"], "保存后内存配置应更新"
assert page.cfg.config["text_polish"]["types"]["工艺要求"]["constraints"] == ["限制A", "限制B", "限制C"], "保存应写回 config.json"
assert dlg.isVisible(), "保存后窗口不应关闭"
# 恢复原角色/限制 (用原始快照, 避免污染后续断言/配置)
dlg.role_edit.setText(orig_role)
dlg.constraints_edit.setPlainText("\n".join(orig_constraints or []))
dlg._save()
print("OK 限制要求窗口: 角色/限制编辑并保存生效")

# polish 输入组装: 所有类型 raw=模板编辑框, system 不重复模板 (与烧录指导一致)
import app.pages.text_polish_page as m
captured = {}
class FakeThread:
    class _Sig:
        def connect(self, *a, **k):
            pass
    succeeded = _Sig()
    failed = _Sig()
    finished = _Sig()
    def __init__(self, *a, **k):
        captured["a"] = a
        captured["k"] = k
    def start(self):
        pass
orig_thread = m.DeepSeekThread
m.DeepSeekThread = FakeThread
page.cfg.config.setdefault("power_conversion", {}).setdefault("api", {})["api_key"] = "sk-test"
api = page.cfg.config["power_conversion"]["api"]
api.setdefault("base_url", "https://api.deepseek.com/v1")
api.setdefault("model", "deepseek-chat")

# 烧录指导
for btn in page.type_group.buttons():
    if btn.text() == "烧录指导":
        btn.setChecked(True)
        break
page._on_type_changed()
page.template_preview_edit.setPlainText("ABC 123 XYZ")
try:
    page.polish()
finally:
    pass
k = captured["k"]
assert "ABC 123 XYZ" in captured["a"][1], "烧录指导 prompt 应含模板编辑框内容"
assert "请按以下模板组织文档内容" not in k["system_prompt"], "system 不应重复模板"
assert "限制条件" in k["system_prompt"], "system 应含限制条件"
assert "精通" in k["system_prompt"], "system 应含角色设定"

# 工艺要求 (非烧录) 与烧录指导一致: raw=模板编辑框, system 不含模板段
# (编辑框仍有未保存修改, 切类型触发 dirty 确认, patch discard 模拟「不保存」)
m.TextPolishPage._confirm_unsaved = lambda self, *a, **k: "discard"
for btn in page.type_group.buttons():
    if btn.text() == "工艺要求":
        btn.setChecked(True)
        break
page._on_type_changed()
m.TextPolishPage._confirm_unsaved = orig_confirm
page.template_preview_edit.setPlainText("DEF 456")
page.ai_thread = None  # 重置上次 polish 的 guard
captured = {}
try:
    page.polish()
finally:
    m.DeepSeekThread = orig_thread
k = captured["k"]
assert "DEF 456" in captured["a"][1], "工艺要求 prompt 应含模板编辑框内容"
assert "请按以下模板组织文档内容" not in k["system_prompt"], "工艺要求 system 不应重复模板"
assert "限制条件" in k["system_prompt"], "工艺要求 system 应含限制条件"
print("OK polish: 所有类型模板编辑框内容作为润色输入, system 不含模板段")

# ==================== 模板插图 ====================
# 构造一张真实 PNG (1x1)
PNG_1PX = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8BQDwAEhQGAhKmMIQAAAABJRU5ErkJggg=="
)
img_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "_img_probe.png")
with open(img_path, "wb") as f:
    f.write(PNG_1PX)

# 0. 剪贴板粘贴: 位图 (截图)
p_edit = TemplateEdit()
p_edit.setPlainText("截图:")
mime_img = QMimeData()
mime_img.setImageData(QImage(img_path))
p_edit.insertFromMimeData(mime_img)
assert "data:image/png;base64" in p_edit.toHtml(), "粘贴位图应转 data URI"
assert "\ufffc" in p_edit.toPlainText(), "粘贴位图应有图片占位"

# 0b. 剪贴板粘贴: 本地图片文件 (文件管理器 Ctrl+C 复制)
p_edit2 = TemplateEdit()
p_edit2.setPlainText("文件:")
mime_url = QMimeData()
mime_url.setUrls([QUrl.fromLocalFile(img_path)])
p_edit2.insertFromMimeData(mime_url)
assert "data:image/png;base64" in p_edit2.toHtml(), "粘贴图片文件应转 data URI"
assert "file://" not in p_edit2.toHtml(), "不应残留外部文件链接"
assert "\ufffc" in p_edit2.toPlainText(), "粘贴图片文件应有图片占位"

# 1. TemplateEdit 插入 data URI 图片
edit = TemplateEdit()
edit.setPlainText("一、工具")
edit.textCursor().insertHtml('<img src="data:image/png;base64,%s" />' % base64.b64encode(PNG_1PX).decode("ascii"))
assert "\ufffc" in edit.toPlainText(), "编辑框应含图片占位"
html = edit.toHtml()
assert "data:image/png;base64" in html, "toHtml 应保留 data URI"

# 2. 保存 → 加载往返
saved = _edit_save_text(edit)
assert _is_html_template(saved), "含图模板应存为 HTML"
edit2 = TemplateEdit()
_set_edit_content(edit2, saved)
assert "data:image/png;base64" in edit2.toHtml(), "加载后图片应保留"
assert _plain_with_img_mark(saved) == "一、工具 [图片]".replace(" ", " ") or "一、工具" in _plain_with_img_mark(saved), "纯文本提取应含文本"

# 3. 主页面: 编辑框插图后润色输入含 [图片] 占位, 结果窗口模板保留 HTML
# (编辑框仍有未保存修改, 切类型触发 dirty 确认, patch discard 模拟「不保存」)
m.TextPolishPage._confirm_unsaved = lambda self, *a, **k: "discard"
for btn in page.type_group.buttons():
    if btn.text() == "烧录指导":
        btn.setChecked(True)
        break
page._on_type_changed()
m.TextPolishPage._confirm_unsaved = orig_confirm
page.chip_combo.blockSignals(True)
page.chip_combo.setCurrentText(chips[0])
page.chip_combo.blockSignals(False)
page._update_template_preview()
base_txt = page.template_preview_edit.toPlainText()
page.template_preview_edit.textCursor().insertHtml(
    '<img src="data:image/png;base64,%s" />' % base64.b64encode(PNG_1PX).decode("ascii")
)
assert "\ufffc" in page.template_preview_edit.toPlainText(), "主页面编辑框应含图片"
page.ai_thread = None  # 重置上次 polish 的 guard
captured = {}
class FakeThread2:
    class _Sig:
        def connect(self, *a, **k):
            pass
    succeeded = _Sig()
    failed = _Sig()
    finished = _Sig()
    def __init__(self, *a, **k):
        captured["a"] = a
        captured["k"] = k
    def start(self):
        pass
orig_thread = m.DeepSeekThread
m.DeepSeekThread = FakeThread2
dlg_cfg = {}
class FakeDialog:
    def __init__(self, doc_title, cfg, parent):
        dlg_cfg["cfg"] = cfg
    def show(self):
        pass
    def raise_(self):
        pass
    def activateWindow(self):
        pass
    def set_loading(self):
        pass
orig_dialog = m.PolishResultDialog
m.PolishResultDialog = FakeDialog
page.cfg.config.setdefault("power_conversion", {}).setdefault("api", {})["api_key"] = "sk-test"
api = page.cfg.config["power_conversion"]["api"]
api.setdefault("base_url", "https://api.deepseek.com/v1")
api.setdefault("model", "deepseek-chat")
try:
    page.polish()
finally:
    m.DeepSeekThread = orig_thread
    m.PolishResultDialog = orig_dialog
assert "[图片]" in captured["a"][1], "prompt 应以 [图片] 占位"
assert "data:image/png;base64" not in captured["a"][1], "prompt 不应含图片 base64"
assert "data:image/png;base64" in dlg_cfg["cfg"]["template"], "结果窗口模板应保留图片"

# 4. 手工保存按钮: 编辑 → 点「💾 保存模板」→ 落盘且不再脏
page.template_preview_edit.textCursor().insertHtml(
    '<img src="data:image/png;base64,%s" />' % base64.b64encode(PNG_1PX).decode("ascii")
)
assert page._template_dirty(), "编辑后应判定脏"
page._save_template_clicked()
assert not page._template_dirty(), "手工保存后不应脏"
assert "data:image" in page._loaded_template_text, "保存点应含图片"
os.remove(img_path)
print("OK 模板插图: 内嵌保存/往返加载/润色输入占位 + 手工保存按钮")

# 恢复 config.json (防止测试污染用户配置)
shutil.copy(_cfg_bak, _cfg_path)
os.remove(_cfg_bak)
print("config.json restored")

print("ALL PASS: 所有类型模板即润色内容 + 支持插图")

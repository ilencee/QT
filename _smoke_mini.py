# -*- coding: utf-8 -*-
import os, sys, traceback, faulthandler
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
sys.path.insert(0, r"c:/Users/86249/Desktop/tool")
f = open(r"c:/Users/86249/Desktop/tool/_smoke_out.txt", "w", encoding="utf-8")
faulthandler.enable(file=f)
try:
    from PyQt6.QtWidgets import QApplication
    app = QApplication([])
    f.write("before import page\n"); f.flush()
    from app.pages.programming_software_page import ProgrammingSoftwarePage
    f.write("before construct\n"); f.flush()
    p = ProgrammingSoftwarePage()
    f.write("after construct\n"); f.flush()
    f.write("ALL PASS\n")
except Exception:
    f.write("EXC: %s\n" % traceback.format_exc())
finally:
    f.close()

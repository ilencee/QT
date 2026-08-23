# -*- coding: utf-8 -*-
for f in ["build_exe.bat", "build_exe_onefile.bat"]:
    b = open(f, "rb").read()
    try:
        b.decode("utf-8")
        is_utf8 = True
    except UnicodeDecodeError:
        is_utf8 = False
    print(f, "| UTF-8:", is_utf8, "| CRLF:", b"\r\n" in b, "| BOM:", b[:3] == b"\xef\xbb\xbf",
          "| collect-submodules:", b"--collect-submodules app.pages".replace(b"app.pages", b"").count(b"collect") if b"--collect-submodules" in b else 0)

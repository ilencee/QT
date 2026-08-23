@echo off
rem Overwrite old VC runtime DLLs in Python build env with latest System32 copies.
set "SRC=%WINDIR%\System32"
set "PY=%LOCALAPPDATA%\Programs\Python\Python39"
set "QT=%PY%\lib\site-packages\PyQt6\Qt6\bin"

echo [1/2] Updating Python39 root (VCRUNTIME) ...
for %%F in (VCRUNTIME140.dll VCRUNTIME140_1.dll) do (
    if exist "%PY%\%%F" (
        if not exist "%PY%\%%F.bak" copy /y "%PY%\%%F" "%PY%\%%F.bak" >nul
        copy /y "%SRC%\%%F" "%PY%\%%F" >nul && echo   updated %%F
    )
)

echo [2/2] Updating PyQt6\Qt6\bin ...
for %%F in (VCRUNTIME140.dll VCRUNTIME140_1.dll MSVCP140.dll MSVCP140_1.dll MSVCP140_2.dll CONCRT140.dll) do (
    if exist "%QT%\%%F" (
        if not exist "%QT%\%%F.bak" copy /y "%QT%\%%F" "%QT%\%%F.bak" >nul
        copy /y "%SRC%\%%F" "%QT%\%%F" >nul && echo   updated %%F
    )
)

echo Done. Please rebuild.
pause

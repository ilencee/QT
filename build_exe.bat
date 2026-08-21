@echo off
chcp 65001 >nul
cd /d "%~dp0"

set "APP_NAME=串口调试工具"

echo ============================================
echo  工作助手 - 一键打包脚本 (PyInstaller)
echo ============================================

echo [1/5] 生成图标文件 (assets\app.ico) ...
python -c "from PIL import Image; Image.open('assets/icon.png').save('assets/app.ico', sizes=[(16,16),(32,32),(48,48),(64,64),(128,128),(256,256)])"

echo [2/5] 清理旧的打包产物 ...
if exist build rmdir /s /q build
if exist dist rmdir /s /q dist

echo [3/5] PyInstaller 打包 (one-dir, 无控制台窗口) ...
python -m PyInstaller --noconfirm --clean --onedir --windowed --name "%APP_NAME%" --icon "assets/app.ico" main.py
if errorlevel 1 (
    echo 打包失败!
    pause
    exit /b 1
)

echo [4/5] 复制运行所需资源到 dist\%APP_NAME% ...
copy /y "config.json" "dist\%APP_NAME%\config.json" >nul
if exist "assets" xcopy /e /i /y "assets\*" "dist\%APP_NAME%\assets" >nul
if exist "XW16Pro_StandaloneProgrammer" xcopy /e /i /y "XW16Pro_StandaloneProgrammer" "dist\%APP_NAME%\XW16Pro_StandaloneProgrammer" >nul
if exist "中微爱芯" xcopy /e /i /y "中微爱芯" "dist\%APP_NAME%\中微爱芯" >nul

echo [5/5] 打包完成!
echo 输出目录: dist\%APP_NAME%
echo 主程序:   dist\%APP_NAME%\%APP_NAME%.exe
echo.
echo 注意: XW16Pro_StandaloneProgrammer / 中微爱芯 目录为烧录软件,
echo       已一并复制到输出目录, 烧录软件页面可直接启动对应 exe。
pause

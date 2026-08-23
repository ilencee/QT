@echo off
chcp 65001 >nul
cd /d "%~dp0"

set "APP_NAME=工作助手"

echo ============================================
echo  工作助手 - 一键打包脚本 (PyInstaller)
echo ============================================

echo [1/5] 生成图标文件 (assets\app.ico) ...
python -c "from PIL import Image; Image.open('assets/icon.png').save('assets/app.ico', sizes=[(16,16),(32,32),(48,48),(64,64),(128,128),(256,256)])"

echo [2/5] 清理旧的打包产物 ...
if exist "build\%APP_NAME%" rmdir /s /q "build\%APP_NAME%"
if exist "dist\%APP_NAME%" rmdir /s /q "dist\%APP_NAME%"
REM 只清理本脚本的产物, 保留单文件版 (dist\工作助手_单文件) 与历史产物

echo [3/5] PyInstaller 打包 (one-dir, 无控制台窗口) ...
python -m PyInstaller --noconfirm --clean --onedir --windowed --name "%APP_NAME%" --icon "%~dp0assets\app.ico" main.py
if errorlevel 1 (
    echo 打包失败!
    pause
    exit /b 1
)

echo [4/5] 复制运行所需资源到 dist\%APP_NAME% ...
copy /y "config.json" "dist\%APP_NAME%\config.json" >nul
if exist "assets" xcopy /e /i /y "assets\*" "dist\%APP_NAME%\assets" >nul
if exist "烧录软件" xcopy /e /i /y "烧录软件" "dist\%APP_NAME%\烧录软件" >nul
if exist "串口调试助手" xcopy /e /i /y "串口调试助手" "dist\%APP_NAME%\串口调试助手" >nul
REM 注意: 不要复制 installed_programs_memory.json — 它是每台电脑本机已安装软件的记忆,
REM 属于运行时生成的用户数据, 首次运行会自动在 exe 旁新建, 切勿把作者的记忆打进发布版。

echo [5/5] 打包完成!
echo 输出目录: dist\%APP_NAME%
echo 主程序:   dist\%APP_NAME%\%APP_NAME%.exe
echo.
echo 注意: 烧录软件 / 串口调试助手 目录已一并复制到输出目录,
echo       烧录软件页与串口调试页可直接启动对应 exe。
pause

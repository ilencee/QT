@echo off
chcp 65001 >nul
cd /d "%~dp0"

set "APP_NAME=工作助手"

echo ============================================
echo  工作助手 - 单文件打包脚本 (PyInstaller onefile)
echo ============================================

echo [1/4] 生成图标文件 (assets\app.ico) ...
python -c "from PIL import Image; Image.open('assets/icon.png').save('assets/app.ico', sizes=[(16,16),(32,32),(48,48),(64,64),(128,128),(256,256)])" 2>nul
if errorlevel 1 (
    if exist "assets\app.ico" (
        echo   警告: Pillow 不可用, 沿用已有 assets\app.ico ^(如需更新图标请先安装 Pillow: pip install pillow^)
    ) else (
        echo   错误: 无法生成图标 ^(Pillow 未安装^) 且 assets\app.ico 不存在!
        pause
        exit /b 1
    )
)

echo [2/4] 清理旧的单文件打包产物 ...
if exist "build\%APP_NAME%_onefile" rmdir /s /q "build\%APP_NAME%_onefile"
if exist "dist\%APP_NAME%_单文件" rmdir /s /q "dist\%APP_NAME%_单文件"

echo [3/4] PyInstaller 单文件打包 (onefile, 无控制台窗口) ...
python -m PyInstaller --noconfirm --clean --onefile --windowed --name "%APP_NAME%" --icon "%~dp0assets\app.ico" --collect-submodules app.pages --distpath "dist\%APP_NAME%_单文件" --workpath "build\%APP_NAME%_onefile" --specpath "build\%APP_NAME%_onefile" main.py
if errorlevel 1 (
    echo 打包失败!
    pause
    exit /b 1
)

echo [4/4] 复制运行所需资源到 exe 旁边 ...
copy /y "config.json" "dist\%APP_NAME%_单文件\config.json" >nul
if exist "assets" xcopy /e /i /y "assets\*" "dist\%APP_NAME%_单文件\assets" >nul
if exist "烧录软件" xcopy /e /i /y "烧录软件" "dist\%APP_NAME%_单文件\烧录软件" >nul
if exist "串口调试助手" xcopy /e /i /y "串口调试助手" "dist\%APP_NAME%_单文件\串口调试助手" >nul
REM 注意: 不要复制 installed_programs_memory.json — 首次运行会自动生成在 exe 旁

echo.
echo 打包完成!
echo 输出目录: dist\%APP_NAME%_单文件
echo 主程序:   dist\%APP_NAME%_单文件\%APP_NAME%.exe
echo.
echo 注意:
echo  1. exe 是单文件 (内含 Python/PyQt6), 无 _internal 目录, 便于加入加密软件白名单
echo  2. config.json / assets / 烧录软件 / 串口调试助手 必须与 exe 同目录, 勿单独拷走 exe
echo  3. 首次运行会自动在 exe 旁生成 installed_programs_memory.json (本机软件记忆)
pause

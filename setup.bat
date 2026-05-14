@echo off
chcp 65001 >nul
TITLE MatrixFlow 一键安装
echo ========================================
echo   MatrixFlow 本地扫码服务 - 一键安装
echo ========================================
echo.

:: [0] 检查/下载 social-auto-upload 源代码
if not exist myUtils\login.py (
    echo [0/3] 下载扫码引擎（social-auto-upload）...
    git clone --depth 1 https://github.com/dreammis/social-auto-upload.git _tmp_sau
    if %ERRORLEVEL% NEQ 0 (
        echo 错误: 下载失败，请检查网络
        pause
        exit /b 1
    )
    xcopy /E /Y _tmp_sau\* . >nul
    rmdir /S /Q _tmp_sau
    echo   → 下载完成
)
echo.

echo [1/3] 安装 Python 依赖...
pip install -r requirements.txt flask flask-cors requests 2>&1
if %ERRORLEVEL% NEQ 0 (
    echo 错误: pip 安装失败，请检查 Python 是否已安装
    pause
    exit /b 1
)
echo   → 依赖安装完成
echo.
echo [2/3] 安装 Chromium 浏览器（约 150MB，首次较慢）...
playwright install chromium
if %ERRORLEVEL% NEQ 0 (
    echo 警告: Chromium 安装失败
    echo 请手动运行: playwright install chromium
)
echo.
echo ========================================
echo   安装完成！
echo   双击 start.bat 启动本地扫码服务
echo ========================================
pause

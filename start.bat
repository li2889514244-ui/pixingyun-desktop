@echo off
cd /d "%~dp0"
title MatrixFlow Desktop Companion

echo ========================================
echo   披星云桌面伴侣 v1.1
echo ========================================
echo.

:: Check for Node.js
where node >nul 2>nul
if %errorlevel% neq 0 (
    echo [0/3] 未检测到 Node.js，正在自动安装...
    echo.
    
    :: Download Node.js LTS (portable, no admin needed)
    set NODE_URL=https://registry.npmmirror.com/-/binary/node/v20.18.0/node-v20.18.0-win-x64.zip
    set NODE_ZIP=%TEMP%\node-portable.zip
    set NODE_DIR=%USERPROFILE%\matrixflow-node
    
    if not exist "%NODE_DIR%" (
        echo 正在下载 Node.js (约 28MB)...
        powershell -Command "Invoke-WebRequest -Uri '%NODE_URL%' -OutFile '%NODE_ZIP%'" 2>nul
        if %errorlevel% neq 0 (
            echo 下载失败，请手动安装 Node.js: https://nodejs.org
            pause
            exit /b 1
        )
        echo 正在解压...
        powershell -Command "Expand-Archive -Path '%NODE_ZIP%' -DestinationPath '%NODE_DIR%' -Force" 2>nul
        del "%NODE_ZIP%" 2>nul
    )
    
    :: Use portable node
    set PATH=%NODE_DIR%\node-v20.18.0-win-x64;%PATH%
    echo Node.js 就绪: 
    node --version
    echo.
)

echo [1/3] 安装依赖中...
if not exist node_modules (
    call npm install --registry=https://registry.npmmirror.com 2>nul
    if %errorlevel% neq 0 (
        echo 依赖安装失败，请检查网络连接
        pause
        exit /b 1
    )
)

echo [2/3] 安装浏览器引擎（仅首次）...
call npx playwright install chromium 2>nul

echo [3/3] 启动服务...
echo.
echo 浏览器将自动打开，如未打开请访问 http://localhost:3456
echo 关闭此窗口即可退出程序
echo ========================================
start http://localhost:3456
node server.cjs
pause

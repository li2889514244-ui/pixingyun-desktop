@echo off
chcp 65001 >nul
TITLE MatrixFlow 本地扫码服务
cd /d "%~dp0"

echo ========================================
echo   MatrixFlow 本地扫码服务
echo   http://localhost:5409
echo ========================================
echo.
echo 支持平台: 抖音 / 小红书 / 快手 / 视频号
echo.
echo 在 MatrixFlow 网页中点击"添加平台账号"即可使用
echo.
echo 按 Ctrl+C 停止服务
echo ========================================

python sau_backend.py

pause

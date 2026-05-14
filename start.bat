@echo off
TITLE 披星云桌面伴侣
cd /d "%~dp0"

set PY=
for %%v in (Python312 Python313 Python311 Python310) do (
    if exist "C:\Users\%USERNAME%\AppData\Local\Programs\Python\%%v\pythonw.exe" set PY=C:\Users\%USERNAME%\AppData\Local\Programs\Python\%%v\pythonw.exe
)
if "%PY%"=="" where pythonw >nul 2>&1 && set PY=pythonw
if "%PY%"=="" where python >nul 2>&1 && set PY=python
if "%PY%"=="" echo 请先安装 Python 3.10+ && pause && exit /b 1

start "" "%PY%" "%~dp0MatrixFlow桌面伴侣.pyw"

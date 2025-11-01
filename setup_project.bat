@echo off
echo ========================================
echo PSA Card Downloader - Project Setup
echo ========================================
echo.

REM 检查虚拟环境是否存在
if not exist "venv" (
    echo Virtual environment not found. Creating...
    call setup_venv.bat
    if errorlevel 1 (
        pause
        exit /b 1
    )
)

REM 激活虚拟环境
echo Activating virtual environment...
call venv\Scripts\activate.bat

REM 升级pip
echo.
echo Upgrading pip...
python -m pip install --upgrade pip

REM 安装依赖
echo.
echo Installing dependencies...
pip install -r requirements.txt

if errorlevel 1 (
    echo.
    echo ERROR: Failed to install dependencies
    pause
    exit /b 1
)

echo.
echo ========================================
echo Setup completed successfully!
echo ========================================
echo.
echo Virtual environment is activated.
echo.
echo To start the server, run:
echo   python app.py
echo.
echo To deactivate the virtual environment, run:
echo   deactivate
echo.
pause


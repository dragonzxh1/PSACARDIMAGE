@echo off
echo ========================================
echo Creating Python Virtual Environment
echo ========================================
echo.

REM 检查Python是否安装
python --version >nul 2>&1
if errorlevel 1 (
    echo ERROR: Python is not installed or not in PATH
    echo Please install Python 3.7 or higher
    pause
    exit /b 1
)

echo Python version:
python --version
echo.

REM 创建虚拟环境
echo Creating virtual environment 'venv'...
python -m venv venv
if errorlevel 1 (
    echo ERROR: Failed to create virtual environment
    echo Make sure you have Python 3.7 or higher installed
    pause
    exit /b 1
)

echo.
echo ========================================
echo Virtual environment created successfully!
echo ========================================
echo.
echo To activate the virtual environment, run:
echo   venv\Scripts\activate
echo.
echo Then install dependencies:
echo   pip install -r requirements.txt
echo.
echo Or run the automatic setup:
echo   setup_project.bat
echo.
pause


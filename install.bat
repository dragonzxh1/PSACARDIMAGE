@echo off
echo ========================================
echo Installing Dependencies
echo ========================================
echo.

python -m pip install --upgrade pip

echo.
echo Installing requests...
python -m pip install requests>=2.31.0

echo.
echo Installing beautifulsoup4...
python -m pip install beautifulsoup4>=4.12.0

echo.
echo Installing lxml...
python -m pip install lxml>=4.9.0

echo.
echo Installing flask...
python -m pip install flask>=3.0.0

echo.
echo Installing flask-cors...
python -m pip install flask-cors>=4.0.0

echo.
echo ========================================
echo Installation Complete!
echo ========================================
echo.
echo You can now start the server with:
echo   python app.py
echo   or
echo   python run_server.py
echo.
pause



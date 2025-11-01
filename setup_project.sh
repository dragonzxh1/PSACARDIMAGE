#!/bin/bash

echo "========================================"
echo "PSA Card Downloader - Project Setup"
echo "========================================"
echo

# 检查虚拟环境是否存在
if [ ! -d "venv" ]; then
    echo "Virtual environment not found. Creating..."
    bash setup_venv.sh
    if [ $? -ne 0 ]; then
        exit 1
    fi
fi

# 激活虚拟环境
echo "Activating virtual environment..."
source venv/bin/activate

# 升级pip
echo
echo "Upgrading pip..."
python -m pip install --upgrade pip

# 安装依赖
echo
echo "Installing dependencies..."
pip install -r requirements.txt

if [ $? -ne 0 ]; then
    echo
    echo "ERROR: Failed to install dependencies"
    exit 1
fi

echo
echo "========================================"
echo "Setup completed successfully!"
echo "========================================"
echo
echo "Virtual environment is activated."
echo
echo "To start the server, run:"
echo "  python app.py"
echo
echo "To deactivate the virtual environment, run:"
echo "  deactivate"
echo


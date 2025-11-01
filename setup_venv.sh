#!/bin/bash

echo "========================================"
echo "Creating Python Virtual Environment"
echo "========================================"
echo

# 检查Python是否安装
if ! command -v python3 &> /dev/null; then
    echo "ERROR: Python3 is not installed or not in PATH"
    echo "Please install Python 3.7 or higher"
    exit 1
fi

echo "Python version:"
python3 --version
echo

# 创建虚拟环境
echo "Creating virtual environment 'venv'..."
python3 -m venv venv

if [ $? -ne 0 ]; then
    echo "ERROR: Failed to create virtual environment"
    echo "Make sure you have Python 3.7 or higher installed"
    exit 1
fi

echo
echo "========================================"
echo "Virtual environment created successfully!"
echo "========================================"
echo
echo "To activate the virtual environment, run:"
echo "  source venv/bin/activate"
echo
echo "Then install dependencies:"
echo "  pip install -r requirements.txt"
echo
echo "Or run the automatic setup:"
echo "  ./setup_project.sh"
echo


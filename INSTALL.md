# 安装依赖项指南 / Installation Guide

## 方法1：使用批处理脚本（Windows推荐）

双击运行 `install.bat` 文件，或在命令行中执行：
```bash
install.bat
```

## 方法2：使用pip直接安装

在命令行中执行：
```bash
pip install -r requirements.txt
```

或者使用Python模块：
```bash
python -m pip install -r requirements.txt
```

## 方法3：逐个安装

如果批量安装有问题，可以逐个安装：

```bash
pip install requests>=2.31.0
pip install beautifulsoup4>=4.12.0
pip install lxml>=4.9.0
pip install flask>=3.0.0
pip install flask-cors>=4.0.0
```

## 方法4：使用Python脚本

运行：
```bash
python install_dependencies.py
```

## 验证安装

安装完成后，可以验证依赖是否安装成功：

```bash
python -c "import flask; import flask_cors; import requests; from bs4 import BeautifulSoup; print('All dependencies installed successfully!')"
```

## 常见问题

### 问题1：pip命令未找到
**解决方案：** 使用 `python -m pip` 代替 `pip`

### 问题2：权限错误
**解决方案：** 
- Windows: 以管理员身份运行命令提示符
- 或使用 `--user` 参数：`pip install --user -r requirements.txt`

### 问题3：网络连接问题
**解决方案：**
- 检查网络连接
- 尝试使用国内镜像源：
```bash
pip install -r requirements.txt -i https://pypi.tuna.tsinghua.edu.cn/simple
```

### 问题4：Python版本过低
**解决方案：** 确保使用Python 3.7或更高版本
```bash
python --version
```

## 安装完成后的下一步

安装完依赖后，启动服务器：
```bash
python app.py
```

然后在浏览器中访问：`http://localhost:5000`



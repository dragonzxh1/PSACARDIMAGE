# PowerShell 快速启动指南

## 方法1：使用PowerShell脚本（推荐）

```powershell
.\start.ps1
```

如果遇到执行策略错误，先运行：
```powershell
Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser
```

## 方法2：手动步骤

### 步骤1：创建虚拟环境
```powershell
python -m venv venv
# 或
python3 -m venv venv
```

### 步骤2：激活虚拟环境
```powershell
.\venv\Scripts\Activate.ps1
```

如果出现执行策略错误：
```powershell
Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser
```

### 步骤3：安装依赖
```powershell
pip install -r requirements.txt
```

### 步骤4：启动服务器
```powershell
python app.py
```

## 方法3：使用批处理文件（在PowerShell中）

```powershell
cmd /c setup_project.bat
```

或

```powershell
.\setup_project.bat
```

## 常见问题解决

### 问题1：Python命令找不到
**解决方案：**
- 检查Python是否安装：`python --version` 或 `python3 --version`
- 如果没有，安装Python 3.7或更高版本
- 确保在安装时选择了"Add Python to PATH"

### 问题2：执行策略错误
**错误信息：** `cannot be loaded because running scripts is disabled on this system`

**解决方案：**
```powershell
Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser
```

### 问题3：虚拟环境激活失败
**解决方案：**
```powershell
# 检查虚拟环境是否存在
Test-Path venv

# 如果不存在，重新创建
python -m venv venv

# 激活
.\venv\Scripts\Activate.ps1
```

### 问题4：依赖安装失败
**解决方案：**
```powershell
# 升级pip
python -m pip install --upgrade pip

# 使用国内镜像源（如果网络慢）
pip install -r requirements.txt -i https://pypi.tuna.tsinghua.edu.cn/simple
```

## 启动后

服务器启动成功后，在浏览器中访问：
**http://localhost:5000**


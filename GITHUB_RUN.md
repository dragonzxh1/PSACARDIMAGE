# 如何在GitHub中运行服务

## 方法1：从GitHub克隆到本地运行（推荐）

### 步骤1：克隆仓库
在命令行中执行：
```bash
git clone https://github.com/dragonzxh1/PSACARDIMAGE.git
cd PSACARDIMAGE
```

### 步骤2：创建虚拟环境
**Windows:**
```powershell
python -m venv venv
.\venv\Scripts\activate
```

**Mac/Linux:**
```bash
python3 -m venv venv
source venv/bin/activate
```

### 步骤3：安装依赖
```bash
pip install -r requirements.txt
```

### 步骤4：运行服务
```bash
python app.py
```

### 步骤5：访问服务
打开浏览器访问：`http://localhost:5000`

---

## 方法2：使用GitHub Codespaces（在线运行）

### 步骤1：打开Codespaces
1. 访问你的仓库：https://github.com/dragonzxh1/PSACARDIMAGE
2. 点击绿色的 "Code" 按钮
3. 选择 "Codespaces" 标签
4. 点击 "Create codespace on main"

### 步骤2：等待环境创建
GitHub会自动创建云端开发环境（需要几分钟）

### 步骤3：安装依赖
在打开的终端中执行：
```bash
pip install -r requirements.txt
```

### 步骤4：运行服务
```bash
python app.py
```

### 步骤5：访问服务
Codespaces会显示一个端口转发URL，点击即可访问

---

## 方法3：使用Windows一键启动脚本

如果你在Windows上，可以使用提供的脚本：

```powershell
.\start.ps1
```

这个脚本会自动：
- 检查Python
- 创建虚拟环境
- 安装依赖
- 启动服务

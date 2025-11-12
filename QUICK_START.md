# 快速开始指南 / Quick Start Guide

## Web界面使用 / Web Interface Usage

### 步骤 1: 安装依赖 / Step 1: Install Dependencies

```bash
pip install -r requirements.txt
```

### 步骤 2: 启动服务器 / Step 2: Start Server

**Windows:**
```bash
start_web.bat
```

或直接运行：
```bash
python app.py
```

**Linux/Mac:**
```bash
chmod +x start_web.sh
./start_web.sh
```

或直接运行：
```bash
python3 app.py
```

### 步骤 3: 访问界面 / Step 3: Access Interface

打开浏览器访问：`http://localhost:5000`

### 步骤 4: 使用功能 / Step 4: Use Features

#### 单个下载 / Single Download

1. **输入证书编号** - 在输入框中输入PSA证书编号（如：`96098359`）
2. **选择图片尺寸** - 选择要下载的图片尺寸（原始/大图/中图/小图）
3. **预览图片** - 点击"Preview Images"按钮查看找到的图片URL
4. **下载图片** - 点击"Download Images"按钮自动下载并打包为ZIP文件

#### 批量下载 / Batch Download

1. **准备文件** - 创建一个TXT或Excel文件，每行一个证书编号
2. **切换到批量下载标签** - 点击"Batch Download"标签页
3. **选择图片尺寸** - 选择要下载的图片尺寸
4. **上传文件** - 点击"Choose File"选择您的证书编号文件
5. **开始下载** - 点击"Start Batch Download"开始批量处理
6. **等待完成** - 处理完成后会自动下载包含所有证书图片的ZIP文件

### 语言切换 / Language Switch

点击右上角的"English"或"中文"按钮切换界面语言（默认英文优先）。

## 功能说明 / Features

- ✅ **预览功能**：在下载前先查看找到的图片URL
- ✅ **自动下载**：下载成功后自动触发ZIP文件下载
- ✅ **批量下载**：支持从TXT/Excel文件批量导入证书编号
- ✅ **Item Information提取**：自动提取并保存卡片的详细信息
- ✅ **多尺寸支持**：可选择下载原始、大图、中图或小图
- ✅ **实时反馈**：显示处理状态和错误信息
- ✅ **双语支持**：支持中英文界面切换

## 常见问题 / FAQ

### Q: 如何输入证书编号？
A: 可以直接输入数字（如 `96098359`）或包含前缀的格式（如 `PSAbian78928691`），程序会自动提取数字部分。

### Q: 下载的文件在哪里？
A: ZIP文件会在浏览器中自动下载。图片原始文件保存在服务器的 `downloads/PSA_证书编号/` 目录下。每个证书文件夹中还包含一个 `{证书编号}_item_info.txt` 文件，记录了卡片的详细信息。

### Q: 批量下载支持什么文件格式？
A: 支持TXT文件（每行一个证书编号）和Excel文件（.xlsx或.xls格式）。程序会自动识别文件格式并提取证书编号。

### Q: 批量下载时如何选择图片尺寸？
A: 在批量下载界面中，您可以选择以下尺寸之一：
- **Original**：原始尺寸（最高质量）
- **Large**：大图
- **Medium**：中图
- **Small**：小图

### Q: 如果找不到图片怎么办？
A: 
1. 确认证书编号正确
2. 检查网络连接
3. 尝试手动访问PSA网站确认证书存在
4. 查看服务器控制台的错误信息

## API接口 / API Endpoints

如需编程调用，可以使用以下API：

- `POST /api/download` - 下载单个证书的图片
- `POST /api/batch_download` - 批量下载图片（上传TXT/Excel文件）
- `POST /api/preview` - 预览图片URL
- `GET /api/download_file/<filename>` - 下载ZIP文件
- `GET /api/health` - 健康检查



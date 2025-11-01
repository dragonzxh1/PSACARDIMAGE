# PSA卡片高清图片下载器 / PSA Card Image Downloader

一个专业的PSA认证卡片高清图片下载爬虫工具，支持根据证书编号自动下载卡片的正反面高清图片。

A professional tool for downloading high-resolution images from PSA-certified cards based on certificate numbers.

## 功能特点 / Features

- ✅ 根据PSA证书编号自动访问验证页面 / Automatically access PSA certificate pages
- ✅ 智能提取高清图片下载地址（支持多种URL模式识别） / Intelligent extraction of high-resolution image URLs
- ✅ 自动下载并保存卡片高清图片 / Automatic download and save high-resolution card images
- ✅ 支持进度显示和错误重试机制 / Progress display and error retry mechanism
- ✅ **Web界面支持（中英文双语）** / **Web interface with bilingual support (English/Chinese)**
- ✅ 命令行和编程接口 / Command-line and programming interface

## 安装步骤

1. 安装Python依赖包：
```bash
pip install -r requirements.txt
```

2. 如果需要处理JavaScript渲染的页面，可以安装Selenium（可选）：
```bash
pip install selenium
```

## 使用方法 / Usage

### Web界面（推荐） / Web Interface (Recommended)

1. 启动Web服务器：
```bash
python app.py
```

2. 打开浏览器访问：`http://localhost:5000`

3. 在网页界面中输入PSA证书编号即可下载或预览图片

**Web界面特点 / Web Interface Features:**
- 🌐 支持中英文双语切换 / Bilingual support (English/Chinese)
- 📱 响应式设计，支持移动设备 / Responsive design for mobile devices
- 👁️ 图片预览功能 / Image preview functionality
- 📦 自动打包为ZIP文件下载 / Automatic ZIP file download
- ⚡ 实时状态反馈 / Real-time status feedback

### 命令行使用 / Command Line Usage

运行程序：
```bash
python psa_card_downloader.py
```

然后根据提示输入PSA证书编号，例如：
- `96098359`
- `PSAbian78928691` （程序会自动提取数字部分）

### 编程调用

```python
from psa_card_downloader import PSACardImageDownloader

# 创建下载器实例
downloader = PSACardImageDownloader()

# 下载指定证书编号的图片
downloader.download_images("96098359", save_dir="downloads")
```

### 自定义使用

```python
# 使用日本站点
downloader = PSACardImageDownloader(base_url="https://www.psacard.co.jp/cert")

# 只获取图片URL，不下载
image_urls, title = downloader.get_high_res_images("96098359")
print(f"找到 {len(image_urls)} 张图片")
for url in image_urls:
    print(url)
```

## 图片保存位置

下载的图片会保存在以下目录结构中：
```
downloads/
└── PSA_96098359/
    ├── image_1_xxx.jpg  (正面)
    └── image_2_xxx.jpg  (背面)
```

## URL格式支持

程序支持以下PSA网站格式：
- `https://www.psacard.com/cert/{编号}`
- `https://www.psacard.co.jp/cert/{编号}`

## 技术实现

### 图片URL提取策略

程序采用多种策略来查找高清图片：

1. **HTML标签解析**：查找所有`<img>`标签及其`src`、`data-src`、`data-highres`等属性
2. **CSS背景图片**：从`style`属性中提取背景图片URL
3. **JavaScript数据**：解析页面中的JavaScript代码查找图片URL
4. **URL模式转换**：将缩略图URL转换为高清URL
5. **备用模式匹配**：尝试常见的PSA图片URL模式

### 高清图片识别标准

程序会优先选择包含以下关键词的图片URL：
- `highres`, `high-res`, `high_res`
- `large`, `original`, `full`
- `hd`, `high`, `big`, `max`

同时排除明显不是卡片图片的元素（如logo、图标等）。

## 注意事项

1. **合法使用**：请遵守PSA网站的服务条款和robots.txt规定
2. **请求频率**：程序已内置请求延迟，避免过于频繁的请求
3. **网络连接**：确保网络连接正常，可以访问PSA网站
4. **证书编号**：请输入有效的PSA证书编号

## 故障排除

### 问题：无法找到图片
- 检查证书编号是否正确
- 确认网络连接正常
- 尝试手动访问PSA网站确认证书存在

### 问题：下载的图片是缩略图
- 程序会尝试多种方法查找高清图
- 如果页面使用JavaScript动态加载，可能需要使用Selenium版本

### 问题：下载失败
- 检查保存目录的写入权限
- 确认磁盘空间充足
- 查看错误信息，可能是网络超时导致

## 许可证

本项目仅供学习和研究使用。


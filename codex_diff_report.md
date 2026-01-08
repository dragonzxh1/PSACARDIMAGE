# Codex 分支与本地代码对比报告

## 概述

Codex 分支 `origin/codex/perform-overall-code-review` 对代码进行了以下修改：
- 修改了 `app.py`
- 修改了 `psa_web/__init__.py`（注意：本地代码已重组为 `web/psa_web/__init__.py`）

## 详细差异

### 1. app.py 差异

#### Codex 分支的修改：
```python
import os
from psa_web import create_app

app = create_app()

if __name__ == '__main__':
    debug = os.getenv("PSA_DEBUG", "").lower() in ("1", "true", "yes", "on")
    app.run(debug=debug, host='0.0.0.0', port=5000)
```

**改进点：**
- ✅ 添加了 `import os`
- ✅ 使用 `PSA_DEBUG` 环境变量控制 debug 模式
- ✅ 更灵活的 debug 标志判断

#### 本地代码当前版本：
```python
import os
import sys
from pathlib import Path

# 添加项目根目录到路径
project_root = Path(__file__).resolve().parent
sys.path.insert(0, str(project_root))

from web.psa_web import create_app

app = create_app()

if __name__ == '__main__':
    # 从环境变量读取配置，支持 Sealos 等云平台
    port = int(os.environ.get('PORT', 5000))
    host = os.environ.get('HOST', '0.0.0.0')
    # 默认启用debug模式
    debug = os.environ.get('FLASK_DEBUG', 'True').lower() == 'true'
    
    print(f"Starting server in {'DEBUG' if debug else 'PRODUCTION'} mode")
    
    # 在DEBUG模式下，禁用reloader以避免流式响应中断
    # 如果需要自动重载，可以手动重启服务器
    use_reloader = debug and os.environ.get('FLASK_USE_RELOADER', 'False').lower() == 'true'
    
    app.run(debug=debug, host=host, port=port, use_reloader=use_reloader)
```

**本地代码的优势：**
- ✅ 支持 PORT 和 HOST 环境变量（适合云平台部署）
- ✅ 支持 FLASK_USE_RELOADER 控制
- ✅ 有启动信息输出
- ✅ 路径处理更完善

**建议合并：**
- 可以同时支持 `PSA_DEBUG` 和 `FLASK_DEBUG` 环境变量（向后兼容）

### 2. psa_web/__init__.py 差异

#### Codex 分支的修改：
- 使用旧的目录结构：`psa_web/__init__.py`
- 添加了 `_UnavailableDownloader` 类用于处理未配置的下载器
- 使用 `PSA_VERIFY_SSL` 环境变量控制 SSL 验证
- 只支持 PSA 和 TOC 下载器

#### 本地代码当前版本：
- 使用新的目录结构：`web/psa_web/__init__.py`
- 支持更多下载器：PSA, CGC, TOC, RPA, ACG
- 使用 `CGC_HEADLESS` 环境变量控制 CGC 下载器模式
- 代码结构更完善，支持更多功能

**本地代码的优势：**
- ✅ 支持更多卡片类型（CGC, RPA, ACG）
- ✅ 更好的日志配置
- ✅ 更完善的错误处理

## 建议的合并方案

### 方案1：合并 app.py 的改进

在本地 `app.py` 中同时支持 `PSA_DEBUG` 和 `FLASK_DEBUG`：

```python
# 支持多种 debug 环境变量（向后兼容）
debug_env = os.environ.get('PSA_DEBUG') or os.environ.get('FLASK_DEBUG', 'True')
debug = debug_env.lower() in ('1', 'true', 'yes', 'on')
```

### 方案2：保持本地代码结构

由于本地代码已经重组并支持更多功能，建议：
- ✅ 保持当前的目录结构（`web/psa_web/`）
- ✅ 保持当前的功能（多下载器支持）
- ✅ 可以考虑添加 `PSA_DEBUG` 环境变量支持作为 `FLASK_DEBUG` 的别名

## 总结

| 项目 | Codex 分支 | 本地代码 | 建议 |
|------|-----------|---------|------|
| 目录结构 | 旧结构 | 新结构（已重组） | ✅ 保持本地 |
| 下载器支持 | PSA, TOC | PSA, CGC, TOC, RPA, ACG | ✅ 保持本地 |
| Debug 控制 | PSA_DEBUG | FLASK_DEBUG | ✅ 合并支持两者 |
| 环境变量 | PSA_VERIFY_SSL | CGC_HEADLESS, PORT, HOST | ✅ 保持本地 |
| 功能完整性 | 基础功能 | 完整功能 | ✅ 保持本地 |

**推荐操作：**
1. 保持本地代码结构不变
2. 在 `app.py` 中添加对 `PSA_DEBUG` 的支持（作为 `FLASK_DEBUG` 的别名）
3. 不需要合并 `psa_web/__init__.py` 的更改（本地版本更完善）


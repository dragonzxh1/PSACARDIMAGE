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
    # 支持多种 debug 环境变量（向后兼容 Codex 分支的 PSA_DEBUG）
    # 优先使用 PSA_DEBUG，如果没有则使用 FLASK_DEBUG，默认启用 debug 模式
    debug_env = os.environ.get('PSA_DEBUG') or os.environ.get('FLASK_DEBUG', 'True')
    debug = debug_env.lower() in ('1', 'true', 'yes', 'on')
    
    print(f"Starting server in {'DEBUG' if debug else 'PRODUCTION'} mode")
    
    # 在DEBUG模式下，禁用reloader以避免流式响应中断
    # 如果需要自动重载，可以手动重启服务器
    use_reloader = debug and os.environ.get('FLASK_USE_RELOADER', 'False').lower() == 'true'
    
    app.run(debug=debug, host=host, port=port, use_reloader=use_reloader)


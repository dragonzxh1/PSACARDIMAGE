"""
直接启动服务器 - 带错误检查
Direct server startup with error checking
"""
import sys
import os

def check_dependencies():
    """检查依赖是否已安装"""
    missing = []
    try:
        import flask
        print("[OK] Flask installed")
    except ImportError:
        missing.append("flask")
        print("[MISSING] Flask not installed")
    
    try:
        import flask_cors
        print("[OK] flask-cors installed")
    except ImportError:
        missing.append("flask-cors")
        print("[MISSING] flask-cors not installed")
    
    try:
        import requests
        print("[OK] requests installed")
    except ImportError:
        missing.append("requests")
        print("[MISSING] requests not installed")
    
    try:
        from bs4 import BeautifulSoup
        print("[OK] beautifulsoup4 installed")
    except ImportError:
        missing.append("beautifulsoup4")
        print("[MISSING] beautifulsoup4 not installed")
    
    if missing:
        print("\n" + "="*50)
        print("Missing dependencies. Please install them:")
        print(f"pip install {' '.join(missing)}")
        print("="*50)
        return False
    
    return True

if __name__ == "__main__":
    print("="*50)
    print("PSA Card Image Downloader - Server Startup")
    print("="*50)
    print()
    
    # 检查依赖
    if not check_dependencies():
        sys.exit(1)
    
    print()
    print("="*50)
    print("Starting Flask server...")
    print("Server will be available at: http://localhost:5000")
    print("Press Ctrl+C to stop the server")
    print("="*50)
    print()
    
    # 导入并运行Flask应用
    try:
        from app import app
        app.run(debug=True, host='0.0.0.0', port=5000)
    except KeyboardInterrupt:
        print("\n\nServer stopped by user")
    except Exception as e:
        print(f"\n\nError starting server: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)



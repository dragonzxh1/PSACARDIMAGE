"""
安装依赖项脚本
Install dependencies script
"""
import subprocess
import sys

def install_package(package):
    """安装单个包"""
    try:
        print(f"Installing {package}...")
        subprocess.check_call([sys.executable, "-m", "pip", "install", package])
        print(f"✓ {package} installed successfully")
        return True
    except subprocess.CalledProcessError as e:
        print(f"✗ Failed to install {package}: {e}")
        return False
    except Exception as e:
        print(f"✗ Error installing {package}: {e}")
        return False

def main():
    """主函数"""
    print("=" * 60)
    print("PSA Card Image Downloader - Dependency Installation")
    print("=" * 60)
    print()
    
    # 依赖列表
    dependencies = [
        "requests>=2.31.0",
        "beautifulsoup4>=4.12.0",
        "lxml>=4.9.0",
        "flask>=3.0.0",
        "flask-cors>=4.0.0"
    ]
    
    print("Installing dependencies:")
    print("-" * 60)
    
    failed = []
    for dep in dependencies:
        if not install_package(dep):
            failed.append(dep)
        print()
    
    print("=" * 60)
    if failed:
        print(f"✗ Failed to install {len(failed)} package(s):")
        for dep in failed:
            print(f"  - {dep}")
        print()
        print("Please try installing manually:")
        print(f"python -m pip install {' '.join(failed)}")
        return 1
    else:
        print("✓ All dependencies installed successfully!")
        print()
        print("You can now start the server with:")
        print("  python app.py")
        print("  or")
        print("  python run_server.py")
        return 0

if __name__ == "__main__":
    sys.exit(main())



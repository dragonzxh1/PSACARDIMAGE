"""
检查服务器是否运行
Check if server is running
"""
import sys
import requests

try:
    response = requests.get('http://localhost:5000/api/health', timeout=3)
    if response.status_code == 200:
        print("=" * 60)
        print("✓ Server is running!")
        print("=" * 60)
        print("Visit http://localhost:5000 in your browser")
        print("=" * 60)
        sys.exit(0)
    else:
        print(f"✗ Server returned status code: {response.status_code}")
        sys.exit(1)
except requests.exceptions.ConnectionError:
    print("=" * 60)
    print("✗ Server is not running")
    print("=" * 60)
    print("Please start the server with: python app.py")
    sys.exit(1)
except Exception as e:
    print(f"✗ Error: {e}")
    sys.exit(1)



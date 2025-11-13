import subprocess
import sys
import time

def stop_port_5000():
    """停止所有占用5000端口的进程"""
    try:
        # 使用netstat查找占用5000端口的进程
        result = subprocess.run(
            ['netstat', '-ano'],
            capture_output=True,
            text=True,
            encoding='gbk'
        )
        
        pids = set()
        for line in result.stdout.split('\n'):
            if ':5000' in line and 'LISTENING' in line:
                parts = line.split()
                if len(parts) > 4:
                    pid = parts[-1]
                    if pid.isdigit():
                        pids.add(pid)
        
        if not pids:
            print("没有找到占用5000端口的进程")
            return True
        
        print(f"找到 {len(pids)} 个占用5000端口的进程: {', '.join(pids)}")
        
        # 停止所有进程
        for pid in pids:
            try:
                subprocess.run(['taskkill', '/F', '/PID', pid], 
                             capture_output=True, check=False)
                print(f"已停止进程 {pid}")
            except Exception as e:
                print(f"停止进程 {pid} 时出错: {e}")
        
        # 等待端口释放
        time.sleep(2)
        
        # 再次检查
        result = subprocess.run(
            ['netstat', '-ano'],
            capture_output=True,
            text=True,
            encoding='gbk'
        )
        
        still_listening = False
        for line in result.stdout.split('\n'):
            if ':5000' in line and 'LISTENING' in line:
                still_listening = True
                break
        
        if still_listening:
            print("警告: 仍有进程占用5000端口")
            return False
        else:
            print("成功: 5000端口已释放")
            return True
            
    except Exception as e:
        print(f"错误: {e}")
        return False

if __name__ == '__main__':
    success = stop_port_5000()
    sys.exit(0 if success else 1)


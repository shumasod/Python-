import platform
import psutil
import socket
import uuid
import subprocess
import os
from datetime import datetime

try:
    import GPUtil
except ImportError:
    GPUtil = None

def get_system_info():
    """システムの基本情報を取得"""
    try:
        # より信頼性の高いIP取得方法
        def get_local_ip():
            try:
                # ダミー接続でローカルIPを取得
                s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
                s.connect(("8.8.8.8", 80))
                ip = s.getsockname()[0]
                s.close()
                return ip
            except Exception:
                return socket.gethostbyname(socket.gethostname())
        
        # MAC アドレスの改善された取得方法
        def get_mac_address():
            try:
                mac = uuid.getnode()
                return ':'.join(f'{(mac >> elements) & 0xff:02x}' for elements in range(0, 2*6, 2))[::-1]
            except Exception:
                return "取得できませんでした"
        
        return {
            "OS": platform.system(),
            "OS バージョン": platform.version(),
            "OS リリース": platform.release(),
            "アーキテクチャ": platform.machine(),
            "プロセッサ": platform.processor() or "取得できませんでした",
            "ホスト名": socket.gethostname(),
            "IPアドレス": get_local_ip(),
            "MACアドレス": get_mac_address(),
            "Python バージョン": platform.python_version(),
            "起動時間": datetime.fromtimestamp(psutil.boot_time()).strftime("%Y-%m-%d %H:%M:%S")
        }
    except Exception as e:
        return {"エラー": f"システム情報の取得に失敗: {str(e)}"}

def get_cpu_info():
    """CPU情報を取得"""
    try:
        cpu_freq = psutil.cpu_freq()
        cpu_usage_per_core = psutil.cpu_percent(percpu=True, interval=1)
        
        info = {
            "物理コア数": psutil.cpu_count(logical=False),
            "論理コア数": psutil.cpu_count(logical=True),
            "CPU使用率": f"{psutil.cpu_percent(interval=1):.1f}%"
        }
        
        if cpu_freq:
            info.update({
                "最大周波数": f"{cpu_freq.max:.0f} MHz" if cpu_freq.max else "取得できませんでした",
                "最小周波数": f"{cpu_freq.min:.0f} MHz" if cpu_freq.min else "取得できませんでした", 
                "現在の周波数": f"{cpu_freq.current:.0f} MHz" if cpu_freq.current else "取得できませんでした"
            })
        
        # コアごとの使用率（最初の4つまで表示）
        for i, usage in enumerate(cpu_usage_per_core[:4]):
            info[f"コア {i+1} 使用率"] = f"{usage:.1f}%"
        
        if len(cpu_usage_per_core) > 4:
            info["その他のコア"] = f"あと {len(cpu_usage_per_core) - 4} コア"
            
        return info
    except Exception as e:
        return {"エラー": f"CPU情報の取得に失敗: {str(e)}"}

def get_memory_info():
    """メモリ情報を取得"""
    try:
        memory = psutil.virtual_memory()
        swap = psutil.swap_memory()
        
        return {
            "物理メモリ": {
                "総容量": f"{memory.total / (1024**3):.2f} GB",
                "使用可能": f"{memory.available / (1024**3):.2f} GB",
                "使用中": f"{memory.used / (1024**3):.2f} GB",
                "使用率": f"{memory.percent:.1f}%"
            },
            "スワップメモリ": {
                "総容量": f"{swap.total / (1024**3):.2f} GB" if swap.total > 0 else "0 GB",
                "使用中": f"{swap.used / (1024**3):.2f} GB" if swap.used > 0 else "0 GB",
                "使用率": f"{swap.percent:.1f}%" if swap.total > 0 else "0%"
            }
        }
    except Exception as e:
        return {"エラー": f"メモリ情報の取得に失敗: {str(e)}"}

def get_disk_info():
    """ディスク情報を取得"""
    try:
        partitions = psutil.disk_partitions()
        disk_info = {}
        
        for partition in partitions:
            try:
                # システムパーティションのみ表示（WindowsのCDROMドライブなどをスキップ）
                if 'cdrom' in partition.opts or partition.fstype == '':
                    continue
                    
                partition_usage = psutil.disk_usage(partition.mountpoint)
                disk_info[partition.device] = {
                    "マウントポイント": partition.mountpoint,
                    "ファイルシステム": partition.fstype,
                    "総容量": f"{partition_usage.total / (1024**3):.2f} GB",
                    "使用中": f"{partition_usage.used / (1024**3):.2f} GB",
                    "空き容量": f"{partition_usage.free / (1024**3):.2f} GB",
                    "使用率": f"{partition_usage.percent:.1f}%"
                }
            except (PermissionError, FileNotFoundError):
                continue
        
        return disk_info if disk_info else {"エラー": "アクセス可能なディスクが見つかりません"}
    except Exception as e:
        return {"エラー": f"ディスク情報の取得に失敗: {str(e)}"}

def get_gpu_info():
    """GPU情報を取得"""
    if GPUtil is None:
        return {"注意": "GPUtil モジュールがインストールされていません (pip install gputil)"}
    
    try:
        gpus = GPUtil.getGPUs()
        if not gpus:
            return {"情報": "GPU が検出されませんでした"}
        
        gpu_info = {}
        for i, gpu in enumerate(gpus):
            gpu_info[f"GPU {i}"] = {
                "名前": gpu.name,
                "GPU ID": gpu.id,
                "負荷率": f"{gpu.load * 100:.1f}%",
                "メモリ使用量": f"{gpu.memoryUsed} MB / {gpu.memoryTotal} MB ({gpu.memoryUsed/gpu.memoryTotal*100:.1f}%)",
                "空きメモリ": f"{gpu.memoryFree} MB",
                "温度": f"{gpu.temperature}°C" if gpu.temperature else "取得できませんでした"
            }
        return gpu_info
    except Exception as e:
        return {"エラー": f"GPU情報の取得に失敗: {str(e)}"}

def get_network_info():
    """ネットワーク情報を取得"""
    try:
        network_info = {}
        net_stats = psutil.net_io_counters(pernic=True)
        
        for interface, addresses in psutil.net_if_addrs().items():
            # ローカルバックやVMwareなどの仮想インターフェースは除外
            if interface.startswith(('lo', 'Loopback', 'VMware', 'VirtualBox')):
                continue
                
            interface_info = {"アドレス": []}
            
            for addr in addresses:
                if addr.family == socket.AF_INET:  # IPv4
                    interface_info["アドレス"].append({
                        "IPv4": addr.address,
                        "ネットマスク": addr.netmask
                    })
                elif addr.family == socket.AF_INET6:  # IPv6（最初の1つだけ）
                    if len([a for a in interface_info["アドレス"] if "IPv6" in a]) == 0:
                        interface_info["アドレス"].append({
                            "IPv6": addr.address.split('%')[0]  # ゾーンIDを除去
                        })
            
            # ネットワーク統計を追加
            if interface in net_stats:
                stats = net_stats[interface]
                interface_info["統計"] = {
                    "送信": f"{stats.bytes_sent / (1024**2):.2f} MB",
                    "受信": f"{stats.bytes_recv / (1024**2):.2f} MB"
                }
            
            if interface_info["アドレス"]:  # アドレスがある場合のみ追加
                network_info[interface] = interface_info
        
        return network_info if network_info else {"情報": "アクティブなネットワークインターフェースが見つかりません"}
    except Exception as e:
        return {"エラー": f"ネットワーク情報の取得に失敗: {str(e)}"}

def print_info(category, info, indent=0):
    """情報を整形して表示"""
    spaces = "  " * indent
    print(f"{spaces}{category}:")
    
    if isinstance(info, dict):
        for key, value in info.items():
            if isinstance(value, dict):
                print_info(key, value, indent + 1)
            elif isinstance(value, list):
                print(f"{spaces}  {key}:")
                for item in value:
                    if isinstance(item, dict):
                        for sub_key, sub_value in item.items():
                            print(f"{spaces}    {sub_key}: {sub_value}")
                    else:
                        print(f"{spaces}    {item}")
            else:
                print(f"{spaces}  {key}: {value}")
    elif isinstance(info, list):
        for item in info:
            print(f"{spaces}  {item}")
    else:
        print(f"{spaces}  {info}")

def main():
    """メイン処理"""
    print("=" * 60)
    print("システム情報取得ツール")
    print("=" * 60)
    print(f"実行日時: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print()
    
    # 情報収集
    pc_info = {
        "システム情報": get_system_info(),
        "CPU情報": get_cpu_info(),
        "メモリ情報": get_memory_info(),
        "ディスク情報": get_disk_info(),
        "GPU情報": get_gpu_info(),
        "ネットワーク情報": get_network_info()
    }
    
    # 結果表示
    for category, info in pc_info.items():
        print_info(category, info)
        print()
    
    print("=" * 60)
    print("情報取得完了")

if __name__ == "__main__":
    main()

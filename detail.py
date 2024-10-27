import platform
import psutil
import socket
import uuid
import subprocess
import os

try:
    import GPUtil
except ImportError:
    GPUtil = None

def get_system_info():
    try:
        return {
            "OS": platform.system(),
            "OS Version": platform.version(),
            "OS Release": platform.release(),
            "Architecture": platform.machine(),
            "Processor": platform.processor(),
            "Hostname": socket.gethostname(),
            "IP Address": socket.gethostbyname(socket.gethostname()),
            "MAC Address": ':'.join(['{:02x}'.format((uuid.getnode() >> elements) & 0xff) for elements in range(0,2*6,2)][::-1]),
        }
    except Exception as e:
        return {"Error": f"Failed to get system info: {str(e)}"}

def get_cpu_info():
    try:
        cpu_freq = psutil.cpu_freq()
        return {
            "Physical cores": psutil.cpu_count(logical=False),
            "Total cores": psutil.cpu_count(logical=True),
            "Max Frequency": f"{cpu_freq.max:.2f}MHz",
            "Min Frequency": f"{cpu_freq.min:.2f}MHz",
            "Current Frequency": f"{cpu_freq.current:.2f}MHz",
            "CPU Usage": f"{psutil.cpu_percent()}%"
        }
    except Exception as e:
        return {"Error": f"Failed to get CPU info: {str(e)}"}

def get_memory_info():
    try:
        memory = psutil.virtual_memory()
        return {
            "Total": f"{memory.total / (1024**3):.2f} GB",
            "Available": f"{memory.available / (1024**3):.2f} GB",
            "Used": f"{memory.used / (1024**3):.2f} GB",
            "Percentage": f"{memory.percent}%"
        }
    except Exception as e:
        return {"Error": f"Failed to get memory info: {str(e)}"}

def get_disk_info():
    try:
        partitions = psutil.disk_partitions()
        disk_info = {}
        for partition in partitions:
            try:
                partition_usage = psutil.disk_usage(partition.mountpoint)
            except PermissionError:
                continue
            disk_info[partition.device] = {
                "Mountpoint": partition.mountpoint,
                "File system type": partition.fstype,
                "Total Size": f"{partition_usage.total / (1024**3):.2f} GB",
                "Used": f"{partition_usage.used / (1024**3):.2f} GB",
                "Free": f"{partition_usage.free / (1024**3):.2f} GB",
                "Percentage": f"{partition_usage.percent}%"
            }
        return disk_info
    except Exception as e:
        return {"Error": f"Failed to get disk info: {str(e)}"}

def get_gpu_info():
    if GPUtil is None:
        return {"Error": "GPUtil module not installed"}
    
    try:
        gpus = GPUtil.getGPUs()
        gpu_info = {}
        for i, gpu in enumerate(gpus):
            gpu_info[f"GPU {i}"] = {
                "Name": gpu.name,
                "ID": gpu.id,
                "Load": f"{gpu.load*100:.2f}%",
                "Free Memory": f"{gpu.memoryFree}MB",
                "Used Memory": f"{gpu.memoryUsed}MB",
                "Total Memory": f"{gpu.memoryTotal}MB",
                "Temperature": f"{gpu.temperature} °C"
            }
        return gpu_info
    except Exception as e:
        return {"Error": f"Failed to get GPU info: {str(e)}"}

def get_network_info():
    try:
        network_info = {}
        for interface, addresses in psutil.net_if_addrs().items():
            network_info[interface] = []
            for addr in addresses:
                network_info[interface].append({
                    "Address": addr.address,
                    "Netmask": addr.netmask,
                    "Family": str(addr.family)
                })
        return network_info
    except Exception as e:
        return {"Error": f"Failed to get network info: {str(e)}"}

def main():
    pc_info = {
        "System Information": get_system_info(),
        "CPU Information": get_cpu_info(),
        "Memory Information": get_memory_info(),
        "Disk Information": get_disk_info(),
        "GPU Information": get_gpu_info(),
        "Network Information": get_network_info()
    }

    for category, info in pc_info.items():
        print(f"\n{category}:")
        if isinstance(info, dict):
            for key, value in info.items():
                if isinstance(value, dict):
                    print(f"  {key}:")
                    for sub_key, sub_value in value.items():
                        print(f"    {sub_key}: {sub_value}")
                else:
                    print(f"  {key}: {value}")
        elif isinstance(info, list):
            for item in info:
                print(f"  {item}")

if __name__ == "__main__":
    main()
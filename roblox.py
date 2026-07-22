import subprocess
import time

def is_running(package):
    try:
        res = subprocess.run(["su", "-c", f"pidof {package}"], capture_output=True, text=True, stdin=subprocess.DEVNULL)
        return bool(res.stdout.strip())
    except Exception:
        return False

def force_stop(package):
    subprocess.run(["am", "force-stop", package], capture_output=True, text=True)

def launch_game(package):
    cmd = f"su -c 'cmd package resolve-activity --brief {package}'"
    res = subprocess.run(cmd, shell=True, capture_output=True, text=True)
    
    activity = next((line.strip() for line in res.stdout.splitlines() if "/" in line), f"{package}/com.roblox.client.ActivitySplash")
    launch = subprocess.run(["su", "-c", f"am start -n {activity}"], capture_output=True, text=True)
    return launch.returncode == 0

def join_private_server(package, config):
    method = config.get("join_method")
    link = config.get("private_server_link", "").strip() if method == "private_server" else config.get("ps_tiap_akun", {}).get(package, "").strip()

    if link:
        print(f"[*] {package}: Injecting Link Private Server...")
        # Hilangkan shell=True dan pakai format list agar link '&' tidak terputus di terminal
        cmd = [
            "su", 
            "-c", 
            f"am start -a android.intent.action.VIEW -c android.intent.category.BROWSABLE -d '{link}' {package}"
        ]
        
        subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        time.sleep(10) # Kasih jeda 10 detik buat double-tap
        subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

def check_in_game_error(package):
    try:
        cmd_find = f"su -c 'ls -t /sdcard/Android/data/{package}/files/logs/*.log 2>/dev/null | head -n 1'"
        res_find = subprocess.run(cmd_find, shell=True, capture_output=True, text=True, stdin=subprocess.DEVNULL)
        log_file = res_find.stdout.strip()
        
        if not log_file:
            cmd_find = f"su -c 'ls -t /data/data/{package}/files/logs/*.log 2>/dev/null | head -n 1'"
            res_find = subprocess.run(cmd_find, shell=True, capture_output=True, text=True, stdin=subprocess.DEVNULL)
            log_file = res_find.stdout.strip()

        if log_file:
            cmd_check = f"su -c 'tail -n 30 {log_file} | grep -iE -m 1 \"error 278|error 277|error 268|connection lost|disconnect\"'"
            res_check = subprocess.run(cmd_check, shell=True, capture_output=True, text=True, stdin=subprocess.DEVNULL)
            return bool(res_check.stdout.strip())
    except Exception:
        pass
    return False
    

import os
import json
import subprocess
from pathlib import Path

CONFIG_FILE = Path.home() / ".roblox_rejoiner.json"

DEFAULT_CONFIG = {
    "packages": [],
    "reconnect_minutes": 5, 
    "force_close_delay": 30,
    "staggered_delay_min": 25,
    "staggered_delay_max": 40,
    "join_method": "private_server",
    "private_server_link": "",
    "ps_tiap_akun": {},
}

def scan_packages():
    result = subprocess.run(["pm", "list", "packages"], capture_output=True, text=True)
    return sorted(set(
        line.replace("package:", "").strip() 
        for line in result.stdout.splitlines() 
        if "roblox" in line.lower() or "rbx" in line.lower()
    ))

def load_config():
    config = DEFAULT_CONFIG.copy()
    if CONFIG_FILE.exists():
        try:
            with open(CONFIG_FILE, "r") as f:
                config.update(json.load(f))
        except Exception:
            pass
    return config

def save_config(config):
    with open(CONFIG_FILE, "w") as f:
        json.dump(config, f, indent=4)

def setup_config():
    config = load_config()
    print("=== SETUP AUTO REJOINER ===")
    
    # Setup Packages
    packages = scan_packages()
    if not packages:
        print("[-] Tidak ada aplikasi Roblox yang terdeteksi.")
        return None
        
    for i, pkg in enumerate(packages, 1):
        print(f"[{i}] {pkg}")
    
    pilihan = input("Pilih aplikasi (pisahkan dengan koma, misal: 1,2): ")
    terpilih = [packages[int(x.strip()) - 1] for x in pilihan.split(",") if x.strip().isdigit()]
    config["packages"] = terpilih

    # Setup Method
    print("\n[1] PS Global | [2] PS Tiap Akun")
    metode = input("Pilih metode (1/2): ").strip()
    
    if metode == "1":
        config["join_method"] = "private_server"
        config["private_server_link"] = input("Link Private Server: ").strip()
    else:
        config["join_method"] = "private_server_tiap_akun"
        for pkg in terpilih:
            config["ps_tiap_akun"][pkg] = input(f"Link PS untuk {pkg}: ").strip()

    save_config(config)
    print("\n[+] Config tersimpan!")
    return config
    

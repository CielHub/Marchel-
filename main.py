import time
import threading
import random
from config import load_config, setup_config, CONFIG_FILE
from roblox import is_running, force_stop, launch_game, join_private_server, check_in_game_error

recovery_lock = threading.Lock()

class CloneMonitor:
    def __init__(self, package, config):
        self.package = package
        self.config = config
        self.is_online = False
        self.is_recovering = False
        self.last_log_check = time.time()
        self.last_recover = time.time()

    def check_status(self):
        if self.is_recovering:
            return

        alive = is_running(self.package)
        now = time.time()
        
        if alive:
            self.is_online = True
            # Baca log error tiap 20 detik sekali agar CPU tidak berat
            if now - self.last_log_check > 20:
                self.last_log_check = now
                if check_in_game_error(self.package):
                    print(f"[!] {self.package}: Error in-game terdeteksi!")
                    self.is_online = False 
        else:
            self.is_online = False

    def trigger_recovery(self, delay):
        def _recover_task():
            with recovery_lock: # Antrean recovery agar HP tidak hang
                print(f"[*] {self.package}: Memulai proses recovery...")
                force_stop(self.package)
                time.sleep(delay)
                
                if launch_game(self.package):
                    time.sleep(15) # Tunggu engine siap
                    join_private_server(self.package, self.config)
                    
                self.is_recovering = False
                self.is_online = True
                self.last_recover = time.time()
                print(f"[+] {self.package}: Recovery selesai.")

        self.is_recovering = True
        self.is_online = False
        threading.Thread(target=_recover_task, daemon=True).start()

def main():
    if not CONFIG_FILE.exists():
        config = setup_config()
        if not config: return
    else:
        config = load_config()

    packages = config.get("packages", [])
    if not packages:
        print("[-] Tidak ada package di config.")
        return

    monitors = [CloneMonitor(pkg, config) for pkg in packages]
    reconnect_minutes = config.get("reconnect_minutes", 5)
    force_close_delay = config.get("force_close_delay", 30)
    
    print("\n[+] Auto Rejoiner Minimalist Berjalan. Tekan Ctrl+C untuk berhenti.\n")

    try:
        while True:
            for monitor in monitors:
                monitor.check_status()

                # Trigger Recovery Logic
                if not monitor.is_recovering:
                    butuh_recovery = False
                    
                    if not monitor.is_online:
                        butuh_recovery = True
                    elif reconnect_minutes > 0 and (time.time() - monitor.last_recover) >= (reconnect_minutes * 60):
                        print(f"[*] {monitor.package}: Auto-reconnect terjadwal.")
                        butuh_recovery = True

                    if butuh_recovery:
                        monitor.trigger_recovery(force_close_delay)

            time.sleep(2) # Global delay loop 
            
    except KeyboardInterrupt:
        print("\n[!] Dihentikan user. Force close semua clone...")
        for pkg in packages:
            force_stop(pkg)
        print("[+] Keluar dengan bersih.")

if __name__ == "__main__":
    main()
  

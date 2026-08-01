import time
import subprocess
import threading

class Launcher:
    """
    Sub-Sistem Eksekusi Aplikasi (Multi-Package Target).
    Dilengkapi dengan Serialization Lock (Mutex) untuk mencegah Android
    menjadi hang/freeze jika 5 aplikasi direstart secara bersamaan.
    """
    
    def __init__(self, config, logger, events, states):
        self.config = config
        self.logger = logger
        self.events = events
        self.states = states
        
        self.target_activity = self.config.get("target_activity", "com.roblox.client.Activity")
        self.stop_delay = self.config.get("launcher_stop_delay", 3)
        self.deeplink_url = self.config.get("roblox_deeplink", "")
        
        # MUTEX LOCK: Sangat krusial. Memastikan jika 5 package crash bersamaan,
        # sistem akan memulihkannya satu per satu, tidak meledakkan CPU.
        self._recovery_lock = threading.Lock()

    def _run_shell_cmd(self, cmd_list, timeout_sec=15):
        """Eksekusi cangkang (shell) dengan pengaman OOM OS."""
        try:
            subprocess.run(
                cmd_list,
                stdout=subprocess.DEVNULL, 
                stderr=subprocess.DEVNULL, 
                timeout=timeout_sec,
                check=False
            )
            return True
        except subprocess.TimeoutExpired:
            self.logger.error(f"Timeout OS saat mengeksekusi launcher.")
            return False
        except Exception as e:
            self.logger.error(f"Galat tingkat OS pada Launcher: {e}")
            return False

    def force_stop(self, package_name):
        """Mematikan secara paksa satu paket spesifik."""
        self.logger.info(f"[{package_name}] Force-stop (Mengosongkan RAM)...")
        cmd = ["su", "-c", f"am force-stop {package_name}"]
        self._run_shell_cmd(cmd, timeout_sec=10)

    def start_app(self, package_name):
        """
        Meluncurkan paket secara bersih.
        Tetap menyertakan flag FLAG_ACTIVITY_NEW_TASK | FLAG_ACTIVITY_CLEAR_TASK (0x10008000)
        karena ini aman dan valid untuk mode Freeform (mengganti stack lama yang crash).
        """
        self.logger.info(f"[{package_name}] Meluncurkan package...")
        
        if self.deeplink_url:
            cmd = [
                "su", "-c", 
                f"am start -W -f 0x10008000 -a android.intent.action.VIEW -d '{self.deeplink_url}' {package_name}"
            ]
        else:
            cmd = [
                "su", "-c",
                f"am start -W -f 0x10008000 -n {package_name}/{self.target_activity}"
            ]

        success = self._run_shell_cmd(cmd, timeout_sec=20) 
        if not success:
            self.logger.warning(f"[{package_name}] Respons peluncuran melampaui timeout OS.")

    def trigger_recovery(self, package_name):
        """
        Sekuens pemulihan untuk package tertentu.
        Dibungkus dalam antrean (lock) agar OS Android dapat bernapas 
        jika terjadi pemulihan ganda beruntun.
        """
        # Jika lock sedang dipakai oleh package lain, thread akan antre di sini
        with self._recovery_lock:
            self.logger.warning(f"[{package_name}] >> Menjalankan Recovery Sequence...")
            self.states.update(package_name, "recovery_status", "IN_PROGRESS")
            
            # 1. Matikan tuntas
            self.force_stop(package_name)
            
            # 2. Beri jeda Android mendinginkan I/O dan Surface Flinger (Grafis)
            time.sleep(self.stop_delay)
            
            # 3. Luncurkan ulang
            self.start_app(package_name)
            
            self.states.update(package_name, "recovery_status", "COMPLETED")
            self.logger.info(f"[{package_name}] >> Recovery Selesai.")
            
            self.events.publish("RECOVERY_COMPLETED", package_name=package_name)
            
            # Jeda antar recovery agar jika 5 package antre, CPU tidak spike
            time.sleep(2)
            

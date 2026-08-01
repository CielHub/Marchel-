import time
import subprocess

class Launcher:
    """
    Bertanggung jawab atas eksekusi pemulihan aplikasi target (Roblox).
    Berinteraksi langsung dengan subsistem ActivityManager (am) Android via akses root.
    """
    
    def __init__(self, config, logger, events, states):
        self.config = config
        self.logger = logger
        self.events = events
        self.states = states
        
        # Konfigurasi target
        self.target_package = self.config.get("target_package", "com.roblox.client")
        self.target_activity = self.config.get("target_activity", "com.roblox.client.Activity")
        
        # Jeda waktu (detik) antara mematikan dan menghidupkan aplikasi
        # Memberikan OS Android waktu untuk membersihkan Dalvik Heap dan Surface Flinger (VRAM)
        self.stop_delay = self.config.get("launcher_stop_delay", 3)

    def _run_shell_cmd(self, cmd_list, timeout_sec=15):
        """
        Eksekusi perintah shell root dengan aman.
        Mencegah kebuntuan (deadlock) pada sistem Termux apabila OS Android sedang lag ekstrem.
        """
        try:
            subprocess.run(
                cmd_list,
                stdout=subprocess.DEVNULL, # Keluaran am start/force-stop tidak diperlukan
                stderr=subprocess.DEVNULL, # Membuang limbah buffer
                timeout=timeout_sec,
                check=False
            )
            return True
        except subprocess.TimeoutExpired:
            self.logger.error(f"Timeout ({timeout_sec}s) saat mengeksekusi perintah peluncuran.")
            return False
        except Exception as e:
            self.logger.error(f"Galat sistem saat memanggil shell root: {e}")
            return False

    def force_stop(self):
        """
        Menghentikan paksa aplikasi untuk memastikan memori dibersihkan sebelum restart.
        Menggunakan akses root karena Termux tidak memiliki privilese sistem.
        """
        self.logger.info(f"Menghentikan paksa (force-stop) paket: {self.target_package}...")
        
        cmd = ["su", "-c", f"am force-stop {self.target_package}"]
        success = self._run_shell_cmd(cmd, timeout_sec=10)
        
        if success:
            self.logger.info("Perintah force-stop berhasil dieksekusi.")
        else:
            self.logger.warning("Gagal atau terjadi delay saat force-stop.")

    def start_app(self):
        """
        Meluncurkan aplikasi menggunakan Intent Android.
        Menerapkan bendera pembersihan aktivitas (FLAG_ACTIVITY_NEW_TASK | FLAG_ACTIVITY_CLEAR_TASK)
        dalam format heksadesimal (0x10008000) untuk mencegah kebocoran memori UI 
        karena penumpukan tumpukan aktivitas (Activity Stack).
        """
        self.logger.info("Meluncurkan ulang aplikasi target...")
        
        deeplink_url = self.config.get("roblox_deeplink", "")
        
        if deeplink_url:
            # Menggunakan skema deeplink (contoh: roblox://placeId=...)
            cmd = [
                "su", "-c", 
                f"am start -W -f 0x10008000 -a android.intent.action.VIEW -d '{deeplink_url}' {self.target_package}"
            ]
        else:
            # Menggunakan skema Activity standar
            cmd = [
                "su", "-c",
                f"am start -W -f 0x10008000 -n {self.target_package}/{self.target_activity}"
            ]

        # Waktu tunggu ekstra diberikan (20 detik) karena am start dengan parameter -W
        # akan menunggu hingga aplikasi benar-benar merender frame pertama (Cold Start).
        success = self._run_shell_cmd(cmd, timeout_sec=20) 
        
        if success:
            self.logger.info("Perintah peluncuran (am start) berhasil.")
        else:
            self.logger.error("Peluncuran tertunda atau gagal merespons.")

    def trigger_recovery(self):
        """
        Sekuens pemulihan penuh (Recovery Sequence).
        Pemanggilan ini bersifat blocking (sinkron) agar mencegah Monitor 
        memicu perulangan recovery sebelum proses pertama selesai (mencegah Race Condition).
        """
        self.logger.warning("Memulai Sekuens Pemulihan (Recovery)...")
        self.states.update("recovery_status", "IN_PROGRESS")
        
        # 1. Pastikan aplikasi mati total (menghapus proses zombie)
        self.force_stop()
        
        # 2. Beri waktu bagi subsistem memori Android untuk mendaur ulang RAM
        time.sleep(self.stop_delay)
        
        # 3. Mulai ulang aplikasi secara bersih (Cold Start)
        self.start_app()
        
        self.states.update("recovery_status", "COMPLETED")
        self.logger.info("Sekuens Pemulihan selesai.")
        
        # Siarkan bahwa proses telah usai agar komponen lain (seperti Dashboard) dapat diperbarui
        self.events.publish("RECOVERY_COMPLETED")
      

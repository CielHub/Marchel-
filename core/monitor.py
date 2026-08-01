import time
import subprocess
import gc
import threading

class SystemMonitor:
    """
    Jantung operasional CARRERA-HUB.
    Bertugas memantau status aplikasi target (Roblox) secara terus-menerus
    melalui utilitas shell Android.
    """

    def __init__(self, config, logger, events, states, launcher):
        self.config = config
        self.logger = logger
        self.events = events
        self.states = states
        self.launcher = launcher
        
        self.running = False
        self.target_package = self.config.get("target_package", "com.roblox.client")
        
        # Konfigurasi toleransi
        self.check_interval = self.config.get("monitor_interval", 5)
        self.max_failed_checks = self.config.get("max_failed_checks", 3)
        self.failed_check_count = 0
        
        self.monitor_thread = None

    def _run_shell_cmd(self, cmd_list):
        """
        Mengeksekusi perintah shell Android dengan aman.
        Mencegah deadlock OS buffer dengan timeout dan membuang limbah stderr.
        Tidak menggunakan shell=True untuk meminimalisasi footprint proses anak (Phantom Process Limit).
        """
        try:
            result = subprocess.run(
                cmd_list,
                stdout=subprocess.PIPE,
                stderr=subprocess.DEVNULL,
                text=True,
                timeout=10
            )
            return result.stdout
        except subprocess.TimeoutExpired:
            self.logger.warning(f"Timeout saat mengeksekusi: {' '.join(cmd_list)}")
            return ""
        except Exception as e:
            self.logger.error(f"Gagal mengeksekusi shell command {' '.join(cmd_list)}: {e}")
            return ""

    def _is_process_running(self):
        """Memeriksa apakah proses memiliki PID di memori menggunakan BusyBox/ToyBox via Root."""
        # 'su -c pidof' digunakan karena Termux mungkin tidak memiliki akses /proc/<pid> aplikasi lain
        output = self._run_shell_cmd(["su", "-c", f"pidof {self.target_package}"])
        # Jika ada angka yang dikembalikan, berarti proses hidup
        return bool(output.strip())

    def _is_in_foreground(self):
        """
        Memeriksa apakah aplikasi berada di layar utama.
        Menarik dumpsys window dan mem-parsingnya di Python (menghindari piping shell).
        """
        output = self._run_shell_cmd(["su", "-c", "dumpsys window windows"])
        if not output:
            return False
            
        # Mencari baris mCurrentFocus yang menandakan apa yang sedang tampil di layar
        for line in output.splitlines():
            if "mCurrentFocus" in line:
                if self.target_package in line:
                    return True
                else:
                    return False
        return False

    def _evaluate_system_state(self):
        """Melakukan evaluasi logika terhadap status aplikasi saat ini."""
        is_running = self._is_process_running()
        is_foreground = self._is_in_foreground()

        if is_running and is_foreground:
            # Kondisi normal
            if self.failed_check_count > 0:
                self.logger.info("Aplikasi kembali normal dan terdeteksi di foreground.")
            self.failed_check_count = 0
            self.states.update("roblox_status", "RUNNING")
            
        elif is_running and not is_foreground:
            # Aplikasi hidup tetapi tertutup layar lain / terdorong ke background
            self.failed_check_count += 1
            self.logger.warning(f"Aplikasi di background (Gagal {self.failed_check_count}/{self.max_failed_checks}).")
            self.states.update("roblox_status", "BACKGROUND")
            
        else:
            # Aplikasi tidak ditemukan di RAM (crash/tertutup)
            self.failed_check_count += 1
            self.logger.warning(f"Aplikasi tidak berjalan (Gagal {self.failed_check_count}/{self.max_failed_checks}).")
            self.states.update("roblox_status", "CRASHED_OR_STOPPED")

        # Trigger Recovery jika melebihi ambang batas toleransi
        if self.failed_check_count >= self.max_failed_checks:
            self.logger.error("Batas toleransi kegagalan tercapai. Memulai sekuens recovery...")
            self.states.update("roblox_status", "RECOVERING")
            
            # Publikasikan event agar UI/Modul lain tahu
            self.events.publish("RECOVERY_STARTED")
            
            # Reset counter agar tidak terjadi recovery loop beruntun
            self.failed_check_count = 0 
            
            # Panggil launcher secara sinkron (blocking thread ini) hingga restart selesai
            self.launcher.trigger_recovery()
            
            # Beri waktu tambahan setelah recovery sebelum melanjutkan polling
            time.sleep(self.config.get("post_recovery_delay", 15))

    def _monitor_loop(self):
        """Loop abadi yang diawasi dengan ketat penggunaan resource-nya."""
        self.logger.info("Sistem pemantauan (Monitor Loop) berjalan...")
        iteration_count = 0

        while self.running:
            start_time = time.time()
            
            # Eksekusi pengecekan utama
            self._evaluate_system_state()

            # Manajemen Memori: Membersihkan garbage collector secara paksa setiap 20 siklus
            # untuk menstabilkan footprint RAM di lingkungan Termux/Android.
            iteration_count += 1
            if iteration_count % 20 == 0:
                gc.collect()

            # Menghitung durasi sisa untuk sleep guna mempertahankan interval yang konsisten
            elapsed = time.time() - start_time
            sleep_time = max(1.0, self.check_interval - elapsed)
            
            # Tidur hingga siklus berikutnya
            time.sleep(sleep_time)

    def start(self):
        """Memulai modul di thread terpisah agar tidak memblokir main loop."""
        if self.running:
            return
            
        self.running = True
        self.monitor_thread = threading.Thread(
            target=self._monitor_loop,
            daemon=True,
            name="SystemMonitorThread"
        )
        self.monitor_thread.start()

    def stop(self):
        """Menghentikan siklus pemantauan dengan aman."""
        self.logger.info("Menghentikan SystemMonitor...")
        self.running = False
        if self.monitor_thread and self.monitor_thread.is_alive():
            self.monitor_thread.join(timeout=3.0)
      

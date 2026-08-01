import time
import subprocess
import gc
import threading

class SystemMonitor:
    """
    Sistem Pemantauan Paralel (Multi-Package & Multi-Window).
    Dirancang khusus untuk mengawasi 5-7 aplikasi dalam mode Floating/Freeform Window
    tanpa membebani CPU dengan panggilan shell berulang (O(1) OS Call Complexity).
    """

    def __init__(self, config, logger, events, states, launcher):
        self.config = config
        self.logger = logger
        self.events = events
        self.states = states
        self.launcher = launcher
        
        self.running = False
        
        # Mendukung list package dari konfigurasi
        self.target_packages = self.config.get("target_packages", ["com.roblox.client"])
        
        # Jika user salah mengisi string biasa, konversi menjadi list
        if isinstance(self.target_packages, str):
            self.target_packages = [self.target_packages]

        self.check_interval = self.config.get("monitor_interval", 5)
        self.max_failed_checks = self.config.get("max_failed_checks", 3)
        self.post_recovery_delay = self.config.get("post_recovery_delay", 15)
        
        # Melacak kegagalan per package terisolasi
        self.failed_check_counts = {pkg: 0 for pkg in self.target_packages}
        self.monitor_thread = None

    def _run_shell_cmd(self, cmd_list):
        """Mengeksekusi perintah shell Android dengan proteksi timeout."""
        try:
            result = subprocess.run(
                cmd_list,
                stdout=subprocess.PIPE,
                stderr=subprocess.DEVNULL,
                text=True,
                timeout=12
            )
            return result.stdout
        except subprocess.TimeoutExpired:
            # Tidak melakukan log error berlebihan agar tidak spam
            return ""
        except Exception:
            return ""

    def _evaluate_all_packages(self):
        """
        Melakukan satu kali penarikan status OS untuk semua package.
        O(1) system call, O(N) pengecekan string di memori Python.
        Sangat efisien untuk CPU Android dan menghindari batas Phantom Process.
        """
        # 1. Menarik seluruh proses yang hidup di memori
        ps_output = self._run_shell_cmd(["su", "-c", "ps -A"])
        
        # 2. Menarik seluruh informasi jendela (Freeform/Floating/Fullscreen)
        window_output = self._run_shell_cmd(["su", "-c", "dumpsys window windows"])

        # Jika OS tidak merespons (Lag ekstrem), tunda pengecekan siklus ini
        if not ps_output or not window_output:
            self.logger.warning("OS Android terlambat merespons. Menunggu siklus berikutnya...")
            return

        # 3. Evaluasi setiap package secara independen
        for pkg in self.target_packages:
            
            # Memastikan state diinisialisasi
            self.states.init_package(pkg)

            # Cek apakah aplikasi ada di RAM (Proses hidup)
            is_running = pkg in ps_output
            
            # Cek apakah jendela aplikasi ada di memori grafis (Floating/Active)
            # Kita tidak lagi mencari mCurrentFocus karena freeform window tidak selalu memegangnya
            is_visible = pkg in window_output

            self._process_package_state(pkg, is_running, is_visible)

    def _process_package_state(self, pkg, is_running, is_visible):
        """Logika mesin status (State Machine) untuk tiap individual package."""
        
        # Jika package dihentikan manual oleh user/sistem, lewati pemantauan
        if not self.states.get(pkg, "is_active", True):
            return

        # KONDISI 1: Normal (Hidup dan Terlihat sebagai Floating Window/Fullscreen)
        if is_running and is_visible:
            if self.failed_check_counts[pkg] > 0:
                self.logger.info(f"[{pkg}] Kembali beroperasi normal (Freeform/Visible).")
            self.failed_check_counts[pkg] = 0
            self.states.update(pkg, "roblox_status", "RUNNING")

        # KONDISI 2: Aplikasi hidup di background tapi jendelanya tertutup (Minimize/Glitch)
        elif is_running and not is_visible:
            self.failed_check_counts[pkg] += 1
            self.logger.warning(f"[{pkg}] Window tidak terdeteksi (Gagal {self.failed_check_counts[pkg]}/{self.max_failed_checks}).")
            self.states.update(pkg, "roblox_status", "BACKGROUND_OR_HIDDEN")

        # KONDISI 3: Aplikasi terbunuh (Crash/OOM/LMKD)
        else:
            self.failed_check_counts[pkg] += 1
            self.logger.warning(f"[{pkg}] Proses mati (Gagal {self.failed_check_counts[pkg]}/{self.max_failed_checks}).")
            self.states.update(pkg, "roblox_status", "CRASHED_OR_STOPPED")

        # TRIGGER RECOVERY KHUSUS UNTUK PACKAGE INI
        if self.failed_check_counts[pkg] >= self.max_failed_checks:
            self.logger.error(f"[{pkg}] Batas toleransi terlampaui. Memulai recovery khusus...")
            self.states.update(pkg, "roblox_status", "RECOVERING")
            
            # Memicu launcher (Launcher sudah dilengkapi antrean agar aman)
            self.events.publish("RECOVERY_STARTED", package_name=pkg)
            
            # Eksekusi recovery melalui thread launcher, tidak memblokir monitor loop
            # Kita buat thread lepas (fire and forget) karena Launcher punya Queue Lock sendiri
            threading.Thread(
                target=self._trigger_and_wait,
                args=(pkg,),
                daemon=True,
                name=f"Recovery_{pkg}"
            ).start()
            
            self.failed_check_counts[pkg] = 0 

    def _trigger_and_wait(self, pkg):
        """Jembatan eksekusi pemulihan yang aman."""
        self.launcher.trigger_recovery(pkg)
        time.sleep(self.post_recovery_delay)

    def _monitor_loop(self):
        """Siklus abadi pengawas sistem."""
        self.logger.info(f"Monitor Loop dimulai untuk {len(self.target_packages)} package(s).")
        iteration_count = 0

        while self.running:
            start_time = time.time()
            
            self._evaluate_all_packages()

            # Garbage Collection paksa (Penting: membersihkan sisa dump string besar)
            iteration_count += 1
            if iteration_count % 15 == 0:
                gc.collect()

            elapsed = time.time() - start_time
            sleep_time = max(1.0, self.check_interval - elapsed)
            time.sleep(sleep_time)

    def start(self):
        if self.running:
            return
        self.running = True
        self.monitor_thread = threading.Thread(target=self._monitor_loop, daemon=True, name="SystemMonitorThread")
        self.monitor_thread.start()

    def stop(self):
        self.running = False
        if self.monitor_thread and self.monitor_thread.is_alive():
            self.monitor_thread.join(timeout=3.0)
            

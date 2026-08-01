import os
import sys
import time
import signal
import threading
import subprocess

# Mengimpor modul inti (akan diimplementasikan pada tahap selanjutnya)
# Asumsi: arsitektur modular dipertahankan karena sudah optimal untuk decoupling.
from core.config import Config
from core.logger import Logger
from core.states import StateManager
from core.events import EventBus
from core.monitor import SystemMonitor
from core.launcher import Launcher
from core.ui import Dashboard
from core.cache_cleaner import CacheCleaner

class CarreraHubDaemon:
    """
    Orchestrator utama untuk CARRERA-HUB.
    Bertanggung jawab atas inisialisasi, manajemen lifecycle, dan graceful shutdown
    di lingkungan Termux/Android.
    """
    
    def __init__(self):
        self.running = False
        
        # 1. Inisialisasi Modul Utilitas Dasar
        self.logger = Logger("CARRERA-HUB")
        self.config = Config()
        self.events = EventBus()
        self.states = StateManager()

        # 2. Inisialisasi Subsistem Utama
        # Dependency Injection digunakan agar setiap modul memegang instance yang sama
        self.launcher = Launcher(self.config, self.logger, self.events, self.states)
        self.monitor = SystemMonitor(self.config, self.logger, self.events, self.states, self.launcher)
        self.dashboard = Dashboard(self.config, self.logger, self.states)
        self.cache_cleaner = CacheCleaner(self.config, self.logger)

    def _signal_handler(self, signum, frame):
        """
        Menangkap sinyal terminasi (SIGTERM/SIGINT) untuk memicu graceful shutdown.
        Mencegah daemon terbunuh tiba-tiba yang dapat meninggalkan orphan process.
        """
        self.logger.info(f"Menerima sinyal {signum}. Memulai graceful shutdown...")
        self.running = False
        # Memberitahu seluruh modul untuk mulai membersihkan state mereka
        self.events.publish("SHUTDOWN_REQUESTED")

    def _setup_signals(self):
        """Mendaftarkan penangkap sinyal POSIX ke OS Android/Termux."""
        try:
            signal.signal(signal.SIGTERM, self._signal_handler)
            signal.signal(signal.SIGINT, self._signal_handler)
        except ValueError as e:
            self.logger.warning(f"Gagal mendaftarkan signal handler: {e}")

    def _acquire_wakelock(self):
        """
        Memastikan CPU Android tidak masuk ke deep sleep (Doze mode) 
        menggunakan utilitas bawaan termux-api.
        """
        try:
            subprocess.run(
                ["termux-wake-lock"], 
                stdout=subprocess.DEVNULL, 
                stderr=subprocess.DEVNULL,
                timeout=5
            )
            self.logger.info("Wakelock Termux berhasil diaktifkan.")
        except Exception as e:
            self.logger.warning(f"Tidak dapat mengakuisisi termux-wake-lock (Abaikan jika bukan di Termux): {e}")

    def _release_wakelock(self):
        """Melepas wakelock agar sistem Android dapat beristirahat setelah program mati."""
        try:
            subprocess.run(
                ["termux-wake-unlock"], 
                stdout=subprocess.DEVNULL, 
                stderr=subprocess.DEVNULL,
                timeout=5
            )
            self.logger.info("Wakelock Termux berhasil dilepas.")
        except Exception:
            pass

    def start(self):
        """Entry point untuk menjalankan daemon secara 24/7."""
        self.running = True
        self._setup_signals()
        self._acquire_wakelock()

        self.logger.info("Memulai layanan CARRERA-HUB...")
        self.states.update("system_status", "STARTING")

        # Mengaktifkan thread untuk tugas yang berjalan paralel (asynchronous/non-blocking)
        monitor_thread = threading.Thread(target=self.monitor.start, daemon=True, name="MonitorThread")
        dashboard_thread = threading.Thread(target=self.dashboard.start, daemon=True, name="DashboardThread")

        monitor_thread.start()
        dashboard_thread.start()

        self.states.update("system_status", "RUNNING")

        # Main Event Loop / Watchdog
        try:
            cleanup_interval = self.config.get("cache_clean_interval_sec", 3600)
            last_cleanup_time = time.time()

            while self.running:
                # Sleep ringan untuk mencegah CPU hogging pada main thread (O(1) CPU usage)
                time.sleep(1)

                current_time = time.time()
                # Penjadwalan pembersihan cache periodik yang aman
                if current_time - last_cleanup_time >= cleanup_interval:
                    self.cache_cleaner.run()
                    last_cleanup_time = current_time

        except KeyboardInterrupt:
            self.logger.info("Interupsi manual dari pengguna (Ctrl+C).")
        except Exception as e:
            self.logger.error(f"Terjadi kesalahan fatal pada main orchestrator: {e}", exc_info=True)
        finally:
            self.stop()

    def stop(self):
        """Menghentikan seluruh layanan secara hierarkis dan aman."""
        self.logger.info("Menghentikan layanan CARRERA-HUB...")
        self.running = False
        self.states.update("system_status", "STOPPING")

        # Meminta thread/worker untuk berhenti
        self.monitor.stop()
        self.dashboard.stop()

        self._release_wakelock()
        self.logger.info("CARRERA-HUB telah berhenti sepenuhnya.")
        sys.exit(0)

if __name__ == "__main__":
    # Menghindari eksekusi ganda jika dipanggil tanpa sengaja
    try:
        daemon = CarreraHubDaemon()
        daemon.start()
    except Exception as fatal_err:
        print(f"[FATAL] Gagal menginisialisasi daemon: {fatal_err}")
        sys.exit(1)
        

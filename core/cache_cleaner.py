import os
import time
import glob
import subprocess

class CacheCleaner:
    """
    Sub-sistem pemeliharaan ruang penyimpanan (Storage Maintenance).
    Mendukung iterasi untuk multi-package (5-7 aplikasi) guna mencegah
    penyimpanan internal Android penuh oleh file residu dan cache grafis.
    """

    def __init__(self, config, logger):
        self.config = config
        self.logger = logger
        
        # Mengambil list target dari konfigurasi
        self.target_packages = self.config.get("target_packages", ["com.roblox.client"])
        if isinstance(self.target_packages, str):
            self.target_packages = [self.target_packages]

        self.log_dir = self.config.get("log_dir", "logs")
        self.max_log_age_seconds = self.config.get("max_log_age_days", 3) * 86400

    def _safe_remove(self, filepath):
        """Menghapus file log dengan aman (mencegah crash jika file terkunci oleh logger)."""
        try:
            if os.path.exists(filepath) and os.path.isfile(filepath):
                os.remove(filepath)
        except OSError:
            pass
        except Exception:
            pass

    def _clean_carrera_logs(self):
        """Merotasi dan menghapus log CARRERA-HUB yang usang."""
        if not os.path.exists(self.log_dir):
            return

        current_time = time.time()
        log_pattern = os.path.join(self.log_dir, "*.log*") # Termasuk backup dari RotatingFileHandler
        
        deleted_count = 0
        for log_file in glob.glob(log_pattern):
            try:
                file_mod_time = os.path.getmtime(log_file)
                if current_time - file_mod_time > self.max_log_age_seconds:
                    self._safe_remove(log_file)
                    deleted_count += 1
            except OSError:
                continue

        if deleted_count > 0:
            self.logger.info(f"Pembersihan Log: {deleted_count} berkas arsip lama telah dihapus.")

    def _clean_android_app_cache(self):
        """
        Membersihkan cache memori internal dan eksternal untuk SETIAP package yang terdaftar.
        Menggunakan iterasi untuk mencegah perintah shell menjadi terlalu panjang (string limit)
        dan mengisolasi kegagalan per package.
        """
        for pkg in self.target_packages:
            internal_cache = f"/data/data/{pkg}/cache/*"
            code_cache = f"/data/data/{pkg}/code_cache/*"
            external_cache = f"/sdcard/Android/data/{pkg}/cache/*"

            cmd = [
                "su", "-c",
                f"rm -rf {internal_cache} {code_cache} {external_cache}"
            ]

            try:
                subprocess.run(
                    cmd,
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                    timeout=10,
                    check=False
                )
            except subprocess.TimeoutExpired:
                self.logger.warning(f"Pembersihan Cache [{pkg}] tertunda (Timeout). Dilewati.")
            except Exception as e:
                self.logger.error(f"Galat pembersihan cache [{pkg}]: {e}")
                
        self.logger.info("Pembersihan cache direktori aplikasi selesai.")

    def _trim_system_caches(self):
        """
        Memanggil fungsi 'trim-caches' bawaan OS Android.
        Membantu melegakan RAM dari file yang disimpan OS di memori (Page Cache).
        """
        try:
            subprocess.run(
                ["su", "-c", "pm trim-caches 999G"],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                timeout=20,
                check=False
            )
        except Exception:
            pass

    def run(self):
        """Titik masuk (entry point) untuk siklus pembersihan berkala."""
        self.logger.info("Memulai pemeliharaan penyimpanan (Multi-Package Cache Cleanup)...")
        
        self._clean_carrera_logs()
        self._clean_android_app_cache()
        self._trim_system_caches()
        
        self.logger.info("Pemeliharaan penyimpanan selesai.")


import os
import time
import glob
import subprocess

class CacheCleaner:
    """
    Sub-sistem pemeliharaan ruang penyimpanan (Storage Maintenance).
    Berjalan secara periodik untuk menghapus log lama dan membersihkan
    cache memori Android yang ditinggalkan oleh target aplikasi.
    """

    def __init__(self, config, logger):
        self.config = config
        self.logger = logger
        
        self.target_package = self.config.get("target_package", "com.roblox.client")
        self.log_dir = self.config.get("log_dir", "logs")
        
        # Konversi batas hari dari konfigurasi menjadi detik. Default 3 hari.
        self.max_log_age_seconds = self.config.get("max_log_age_days", 3) * 86400

    def _safe_remove(self, filepath):
        """
        Menghapus berkas dengan proteksi terhadap race condition.
        Jika berkas sedang ditulisi oleh modul logger atau dikunci oleh sistem OS,
        pengecualian akan diabaikan (silent pass) agar tidak membuat crash aplikasi utama.
        """
        try:
            if os.path.exists(filepath) and os.path.isfile(filepath):
                os.remove(filepath)
        except OSError:
            # File in use (terkunci) atau Permission Denied. Diabaikan dengan aman.
            pass
        except Exception:
            # Proteksi lapisan kedua untuk memastikan tidak ada eksepsi yang lolos
            pass

    def _clean_carrera_logs(self):
        """
        Memindai direktori log CARRERA-HUB dan menghapus berkas log
        yang telah melampaui batas retensi umur (max_log_age_seconds).
        """
        if not os.path.exists(self.log_dir):
            return

        current_time = time.time()
        # Mencari semua berkas berakhiran .log dalam direktori log
        log_pattern = os.path.join(self.log_dir, "*.log")
        
        deleted_count = 0
        for log_file in glob.glob(log_pattern):
            try:
                # Mengambil waktu modifikasi terakhir file
                file_mod_time = os.path.getmtime(log_file)
                
                if current_time - file_mod_time > self.max_log_age_seconds:
                    self._safe_remove(log_file)
                    deleted_count += 1
            except OSError:
                continue

        if deleted_count > 0:
            self.logger.info(f"Pembersihan Log: {deleted_count} berkas log lama telah dihapus.")

    def _clean_android_app_cache(self):
        """
        Membersihkan memori cache internal dan eksternal aplikasi target menggunakan akses Root.
        Ini sangat penting karena Android tidak akan merilis cache ini sendiri kecuali
        penyimpanan sistem mencapai batas kritis.
        
        Menggunakan perintah rm -rf langsung pada folder cache lebih aman 
        daripada 'pm clear' yang akan MENGHAPUS DATA LOGIN (user data) aplikasi.
        """
        # Menargetkan cache internal (data/data) dan eksternal (sdcard/Android/data)
        # Serta folder code_cache (Dalvik/ART cache yang sering menyebabkan aplikasi berat)
        internal_cache = f"/data/data/{self.target_package}/cache/*"
        code_cache = f"/data/data/{self.target_package}/code_cache/*"
        external_cache = f"/sdcard/Android/data/{self.target_package}/cache/*"

        # Merakit perintah shell untuk BusyBox/ToyBox
        cmd = [
            "su", "-c",
            f"rm -rf {internal_cache} {code_cache} {external_cache}"
        ]

        try:
            # Timeout 15 detik ditambahkan untuk mencegah proses shell macet (deadlock)
            subprocess.run(
                cmd,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                timeout=15,
                check=False
            )
            self.logger.info(f"Pembersihan Cache: Cache {self.target_package} OS Android berhasil dihapus.")
        except subprocess.TimeoutExpired:
            self.logger.warning("Pembersihan Cache tertunda (Timeout OS Shell). Dilewati untuk siklus ini.")
        except Exception as e:
            self.logger.error(f"Gagal mengeksekusi shell root untuk pembersihan cache: {e}")

    def _trim_system_caches(self):
        """
        Memanggil ActivityManager Android untuk membersihkan cache global secara aman.
        'pm trim-caches' adalah fungsi bawaan OS yang meminta semua aplikasi 
        melepaskan cache memori tanpa menghapus profil pengguna.
        """
        try:
            # 999G (atau nilai besar lainnya) memerintahkan OS untuk mencoba mencapai
            # ruang kosong tersebut, yang akan memicu OS untuk mengosongkan semua cache yg bisa dihapus.
            cmd = ["su", "-c", "pm trim-caches 999G"]
            subprocess.run(
                cmd,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                timeout=20,
                check=False
            )
        except Exception:
            # Gagal menjalankan trim-caches bukanlah hal fatal, diabaikan dengan aman.
            pass

    def run(self):
        """
        Fungsi utama yang akan dipanggil oleh scheduler di main.py.
        Menjalankan seluruh rutin pembersihan secara teratur dan tahan gagal (fail-safe).
        """
        self.logger.info("Memulai siklus pembersihan penyimpanan (Storage Maintenance)...")
        
        self._clean_carrera_logs()
        self._clean_android_app_cache()
        self._trim_system_caches()
        
        self.logger.info("Siklus pembersihan penyimpanan selesai.")
          

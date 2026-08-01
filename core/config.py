import os
import threading

class Config:
    """
    Sistem Manajemen Konfigurasi untuk CARRERA-HUB.
    Mendukung parsing thread-safe. Dioptimalkan untuk membaca
    kebutuhan multi-package (5-7 package) tanpa race condition.
    """
    
    def __init__(self, config_path="config.conf"):
        self.config_path = config_path
        self._lock = threading.Lock()
        
        # Nilai default untuk menjamin stabilitas daemon 24/7
        # meskipun file konfigurasi terhapus atau corrupt.
        self._config_data = {
            # Mendukung list untuk multi-package
            "target_packages": ["com.roblox.client"],
            "target_package": "com.roblox.client", # Backward compatibility
            "monitor_interval": 5,
            "max_failed_checks": 3,
            "launcher_stop_delay": 3,
            "post_recovery_delay": 15,
            "log_dir": "logs",
            "max_log_age_days": 3,
            "cache_clean_interval_sec": 3600,
            "roblox_deeplink": ""
        }
        self.load()

    def load(self):
        """Memuat dan mem-parsing file .conf ke dalam memori secara asinkron-aman."""
        with self._lock:
            if not os.path.exists(self.config_path):
                # Fallback ke example jika config.conf tidak ditemukan
                example_path = "config.example.conf"
                if os.path.exists(example_path):
                    self.config_path = example_path
                else:
                    return # Bertahan dengan nilai default bawaan memori

            try:
                with open(self.config_path, "r", encoding="utf-8") as f:
                    for line in f:
                        line = line.strip()
                        # Lewati baris kosong atau komentar
                        if not line or line.startswith("#"):
                            continue
                        
                        if "=" in line:
                            key, value = line.split("=", 1)
                            key = key.strip()
                            value = value.strip()
                            
                            self._config_data[key] = self._parse_value(value)
            except Exception:
                # Silent fallback. Jika gagal baca (misal I/O error), 
                # konfigurasi yang ada di memori tidak akan rusak.
                pass
                
    def _parse_value(self, value):
        """Engine konversi tipe data otomatis, dirancang sangat ringan."""
        # Konversi ke Integer
        if value.isdigit():
            return int(value)
        
        # Konversi ke Float
        try:
            if "." in value and value.replace(".", "", 1).isdigit():
                return float(value)
        except ValueError:
            pass
            
        # Konversi ke Boolean
        lower_val = value.lower()
        if lower_val in ("true", "yes", "on"):
            return True
        if lower_val in ("false", "no", "off"):
            return False
            
        # PENTING: Deteksi List (Multiple Packages)
        # Contoh di conf: target_packages=com.roblox.client,com.roblox.client2,com.roblox.client3
        if "," in value:
            return [item.strip() for item in value.split(",") if item.strip()]
            
        return value

    def get(self, key, default=None):
        """Mengambil nilai konfigurasi dengan jaminan thread-safe."""
        with self._lock:
            return self._config_data.get(key, default)
            
    def set(self, key, value):
        """Menyimpan nilai konfigurasi saat runtime."""
        with self._lock:
            self._config_data[key] = value

                    

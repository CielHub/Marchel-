import threading

class StateManager:
    """
    Manajemen status (State Management) yang thread-safe.
    Dimodifikasi menggunakan arsitektur multiplexing untuk melacak
    status 5-7 package secara terpisah tanpa tumpang tindih.
    """
    
    def __init__(self):
        self._lock = threading.Lock()
        self._states = {}
        # Struktur data internal di memori:
        # {
        #   "com.roblox.client1": {"roblox_status": "RUNNING", "failed_checks": 0},
        #   "com.roblox.client2": {"roblox_status": "CRASHED", "failed_checks": 2}
        # }

    def init_package(self, package_name):
        """Menginisialisasi kerangka status untuk package baru jika belum terdaftar."""
        with self._lock:
            if package_name not in self._states:
                self._states[package_name] = {
                    "roblox_status": "UNKNOWN",
                    "recovery_status": "IDLE",
                    "is_active": True
                }

    def update(self, package_name, key, value):
        """
        Memperbarui nilai status untuk package tertentu secara aman.
        Melindungi aplikasi dari race condition saat 7 thread beroperasi bersamaan.
        """
        with self._lock:
            if package_name not in self._states:
                self._states[package_name] = {}
            self._states[package_name][key] = value

    def get(self, package_name, key, default=None):
        """Mengambil nilai status spesifik dari suatu package."""
        with self._lock:
            return self._states.get(package_name, {}).get(key, default)

    def get_all(self, package_name=None):
        """
        Mengambil salinan status untuk Dashboard atau Logger.
        Menggunakan metode .copy() agar dictionary tidak termutasi oleh modul luar.
        """
        with self._lock:
            if package_name:
                return self._states.get(package_name, {}).copy()
            
            # Mengembalikan salinan penuh untuk semua package
            return {pkg: data.copy() for pkg, data in self._states.items()}

    def set_global(self, key, value):
        """Menyimpan status yang bersifat global (berlaku untuk keseluruhan sistem, bukan per package)."""
        with self._lock:
            if "GLOBAL_SYSTEM" not in self._states:
                self._states["GLOBAL_SYSTEM"] = {}
            self._states["GLOBAL_SYSTEM"][key] = value

    def get_global(self, key, default=None):
        """Mengambil status global sistem."""
        with self._lock:
            return self._states.get("GLOBAL_SYSTEM", {}).get(key, default)
          

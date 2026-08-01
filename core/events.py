import threading

class EventBus:
    """
    Sistem komunikasi antar-modul (Event Dispatcher) yang thread-safe.
    Mendukung event berbasis spesifik package maupun event global, 
    tanpa memicu kebocoran thread di sistem OS Android.
    """
    
    def __init__(self):
        self._lock = threading.Lock()
        self._subscribers = {}
        # Struktur:
        # {
        #   "RECOVERY_STARTED": [callback_fungsi_1, callback_fungsi_2],
        #   "GLOBAL_SHUTDOWN": [callback_fungsi_3]
        # }

    def subscribe(self, event_name, callback):
        """Mendaftarkan fungsi listener untuk bereaksi saat suatu event terjadi."""
        with self._lock:
            if event_name not in self._subscribers:
                self._subscribers[event_name] = []
            if callback not in self._subscribers[event_name]:
                self._subscribers[event_name].append(callback)

    def publish(self, event_name, package_name=None, **kwargs):
        """
        Menyiarkan event ke semua subscriber yang terdaftar.
        
        Args:
            event_name: Nama event (misal: "CRASH_DETECTED")
            package_name: Target package spesifik. Jika None, dianggap event global.
            **kwargs: Data tambahan (payload) opsional.
        """
        # Salin daftar callback ke memori lokal secara cepat agar
        # thread-lock segera terlepas. Menghindari sistem terkunci (deadlock).
        with self._lock:
            callbacks = self._subscribers.get(event_name, []).copy()

        if not callbacks:
            return

        # Eksekusi callback secara sekuensial.
        # Catatan Stabilitas Android: Kita tidak memutar thread baru untuk tiap callback,
        # karena batas maksimal proses Android sangat ketat. Listener wajib bersifat non-blocking.
        for callback in callbacks:
            try:
                callback(package_name=package_name, **kwargs)
            except Exception:
                # Silent catch: Mencegah error pada satu listener menghentikan listener lainnya.
                pass
              

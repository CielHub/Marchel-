import os
import logging
from logging.handlers import RotatingFileHandler

class Logger:
    """
    Sistem pencatatan log (Logging) yang thread-safe dan I/O efisien.
    Dioptimalkan untuk Android (Flash Storage) agar tidak membuat
    bottleneck atau kehabisan ruang penyimpanan saat memantau 5-7 package.
    """
    
    def __init__(self, name="CARRERA-HUB", log_dir="logs"):
        self.name = name
        self.log_dir = log_dir
        self.logger = None
        
        self._setup_logger()
        
    def _setup_logger(self):
        """Inisialisasi handler dengan proteksi konkurensi (Concurrency)."""
        if not os.path.exists(self.log_dir):
            try:
                os.makedirs(self.log_dir)
            except OSError:
                pass

        self.logger = logging.getLogger(self.name)
        self.logger.setLevel(logging.INFO)
        
        # Mencegah memory leak akibat penumpukan duplikasi log handler 
        # saat object diinisialisasi ulang oleh main process.
        if self.logger.hasHandlers():
            self.logger.handlers.clear()

        # Format diperpendek sedikit agar rendering string di Termux lebih hemat CPU
        formatter = logging.Formatter(
            fmt="%(asctime)s | %(levelname)-7s | %(message)s",
            datefmt="%m-%d %H:%M:%S"
        )

        # 1. Console Handler (Kecepatan tinggi, hanya ke layar)
        console_handler = logging.StreamHandler()
        console_handler.setFormatter(formatter)
        self.logger.addHandler(console_handler)

        # 2. File Handler dengan Rotasi Otomatis (Aman untuk Android Flash Drive)
        log_file = os.path.join(self.log_dir, "carrera-hub.log")
        try:
            # maxBytes=2MB, maksimal menyimpan 3 backup.
            # Log lama otomatis terganti. Mencegah Android crash karena storage penuh.
            file_handler = RotatingFileHandler(
                log_file,
                maxBytes=2 * 1024 * 1024, # 2 MB
                backupCount=3,
                encoding="utf-8"
            )
            file_handler.setFormatter(formatter)
            self.logger.addHandler(file_handler)
        except OSError:
            # Jika akses ditolak oleh OS (Permission issue), log file dilewati
            # Program akan tetap berjalan menggunakan console handler.
            pass

    # Wrapper sederhana agar pemanggilan di modul lain tetap bersih
    def info(self, msg):
        self.logger.info(msg)

    def warning(self, msg):
        self.logger.warning(msg)

    def error(self, msg, exc_info=False):
        self.logger.error(msg, exc_info=exc_info)

    def debug(self, msg):
        self.logger.debug(msg)



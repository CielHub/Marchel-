import os
import time
import threading

class Dashboard:
    """
    Antarmuka Terminal (UI) berbasis TUI (Text-based User Interface).
    Menggunakan ANSI Escape Codes standar Termux untuk merender ulang tabel 
    status 5-7 package secara real-time tanpa mengonsumsi banyak CPU.
    """

    def __init__(self, config, logger, states):
        self.config = config
        self.logger = logger
        self.states = states
        
        self.running = False
        self.ui_thread = None
        
        # Tingkat penyegaran layar (Refresh rate). 
        # 2 detik sangat optimal: tidak membuat layar berkedip, tidak membebani CPU.
        self.refresh_interval = 2.0 
        
        self.target_packages = self.config.get("target_packages", ["com.roblox.client"])
        if isinstance(self.target_packages, str):
            self.target_packages = [self.target_packages]

    def _clear_screen(self):
        """
        Membersihkan layar terminal menggunakan ANSI Escape sequence.
        Sangat cepat dan didukung penuh oleh Termux secara native.
        """
        print('\033c', end='')

    def _render_dashboard(self):
        """
        Merakit dan mencetak tata letak (layout) tabel dashboard ke stdout.
        """
        self._clear_screen()
        
        # HEADER
        print("=" * 60)
        print(" CARRERA-HUB : ANDROID MULTI-INSTANCE DAEMON ".center(60, "="))
        print("=" * 60)
        
        system_status = self.states.get_global("system_status", "UNKNOWN")
        print(f" System Status : {system_status}")
        print(f" Total Target  : {len(self.target_packages)} Package(s)")
        print("-" * 60)
        
        # TABEL HEADER
        # Format: [No] | Package Name                | Status     | Recovery
        print(f" {'No':<3} | {'Package Target':<25} | {'State':<12} | {'Recovery'}")
        print("-" * 60)
        
        # MENGAMBIL DATA SNAPSHOT DARI STATES.PY
        all_states = self.states.get_all()
        
        # ITERASI ISI TABEL
        for idx, pkg in enumerate(self.target_packages, start=1):
            pkg_data = all_states.get(pkg, {})
            
            # Memperpendek nama package jika terlalu panjang agar tabel rapi
            display_pkg = pkg if len(pkg) <= 25 else pkg[:22] + "..."
            
            # Status aplikasi utama
            roblox_state = pkg_data.get("roblox_status", "WAITING")
            
            # Status subsistem pemulihan
            recovery_state = pkg_data.get("recovery_status", "IDLE")
            if recovery_state == "IN_PROGRESS":
                roblox_state = "* RECOVERING *"
                
            print(f" {idx:<3} | {display_pkg:<25} | {roblox_state:<12} | {recovery_state}")

        print("-" * 60)
        print(" Tekan CTRL+C untuk menghentikan daemon secara aman.")
        print("=" * 60)

    def _ui_loop(self):
        """Loop abadi yang menggambar UI di thread terpisah."""
        # Beri jeda sebentar di awal agar log inisialisasi sempat terbaca
        time.sleep(3) 
        
        while self.running:
            try:
                self._render_dashboard()
            except Exception as e:
                # Menjaga agar UI crash tidak membunuh sistem utama
                self.logger.error(f"Gagal merender UI Dashboard: {e}")
                
            time.sleep(self.refresh_interval)

    def start(self):
        """Memulai UI di thread background."""
        if self.running:
            return
        self.running = True
        self.ui_thread = threading.Thread(target=self._ui_loop, daemon=True, name="UIDashboardThread")
        self.ui_thread.start()

    def stop(self):
        """Menghentikan pembaruan UI secara aman."""
        self.running = False
        if self.ui_thread and self.ui_thread.is_alive():
            self.ui_thread.join(timeout=2.0)
        
        # Pembersihan layar terakhir
        self._clear_screen()
        print("CARRERA-HUB dihentikan dengan aman. Sampai jumpa.")



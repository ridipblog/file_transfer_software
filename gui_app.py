"""
gui_app.py - Modern Graphical User Interface for Python Socket File Transfer
Redesigned with a sleek, premium dark-slate aesthetic.
Preserves 100% of socket networking, threads, Pinggy tunnel, and SHA-256 logic.
"""

import os
import sys
import time
import socket
import select
import shutil
import hashlib
import threading
import subprocess
from pathlib import Path

import tkinter as tk
from tkinter import ttk, filedialog, messagebox

# Enable High DPI scaling on Windows
if sys.platform == "win32":
    try:
        import ctypes
        ctypes.windll.shcore.SetProcessDpiAwareness(1)
    except Exception:
        pass

# Ensure current folder is in import path
sys.path.insert(0, str(Path(__file__).parent))

from protocol import (
    DEFAULT_PORT,
    CHUNK_SIZE,
    get_all_ips,
    get_local_ip,
    format_bytes,
    calculate_sha256,
    send_packet,
    recv_packet,
)
import receiver
import sender

# --- DESIGN COLOR PALETTE (Modern Slate Dark Theme) ---
COLOR_BG = "#0b0f19"              # Main window background (deep midnight)
COLOR_CARD = "#131b2e"            # Card/container background
COLOR_CARD_BORDER = "#1f2b45"     # Card border highlight
COLOR_CARD_HEADER = "#19233c"     # Card section header
COLOR_INPUT_BG = "#080c16"        # Text entries / listbox background
COLOR_INPUT_BORDER = "#253352"    # Input borders
COLOR_TEXT = "#f8fafc"            # Primary text (clean white)
COLOR_TEXT_MUTED = "#94a3b8"      # Secondary/hint text (slate-400)
COLOR_TEXT_ACCENT = "#38bdf8"     # Highlight text (cyan-400)

COLOR_PRIMARY = "#2563eb"         # Primary Action Blue (600)
COLOR_PRIMARY_HOVER = "#1d4ed8"   # Primary Hover (700)
COLOR_SUCCESS = "#10b981"         # Success Green
COLOR_SUCCESS_HOVER = "#059669"
COLOR_DANGER = "#ef4444"          # Danger Red
COLOR_DANGER_HOVER = "#dc2626"
COLOR_PURPLE = "#8b5cf6"          # Pinggy Violet
COLOR_PURPLE_HOVER = "#7c3aed"
COLOR_BTN_SEC = "#1e293b"         # Secondary Button Slate
COLOR_BTN_SEC_HOVER = "#334155"


def create_hover_button(parent, text, command, bg=COLOR_BTN_SEC, fg=COLOR_TEXT, hover_bg=COLOR_BTN_SEC_HOVER,
                        font=("Segoe UI", 9, "bold"), padx=12, pady=5, width=None, state=tk.NORMAL):
    """Creates a custom flat button with smooth hover animation."""
    btn = tk.Button(
        parent,
        text=text,
        command=command,
        bg=bg,
        fg=fg,
        activebackground=hover_bg,
        activeforeground=fg,
        relief=tk.FLAT,
        font=font,
        padx=padx,
        pady=pady,
        cursor="hand2",
        bd=0,
        highlightthickness=0,
        state=state
    )
    if width:
        btn.config(width=width)

    def on_enter(e):
        if btn["state"] == tk.NORMAL:
            btn.config(bg=hover_bg)

    def on_leave(e):
        if btn["state"] == tk.NORMAL:
            btn.config(bg=bg)

    btn.bind("<Enter>", on_enter)
    btn.bind("<Leave>", on_leave)
    btn._default_bg = bg
    btn._hover_bg = hover_bg
    return btn


class FileTransferGUI:
    def __init__(self, root: tk.Tk):
        self.root = root
        self.root.title("Python Socket File Transfer - Pro Studio")
        self.root.geometry("860x720")
        self.root.minsize(780, 620)
        self.root.config(bg=COLOR_BG)

        # Style configuration for ttk widgets
        self.style = ttk.Style()
        try:
            self.style.theme_use("clam")
        except Exception:
            pass

        self._configure_ttk_styles()

        # Receiver State
        self.server_thread = None
        self.server_running = False
        self.listening_sockets = []
        self.pinggy_process = None
        self.pinggy_url = ""

        # Sender State
        self.sender_thread = None
        self.sender_running = False
        self.items_to_send = []

        self.setup_ui()

    def _configure_ttk_styles(self):
        """Configure dark theme styles for Progressbar and Scrollbars."""
        self.style.configure(
            "Dark.Horizontal.TProgressbar",
            troughcolor=COLOR_INPUT_BG,
            background=COLOR_PRIMARY,
            bordercolor=COLOR_CARD_BORDER,
            lightcolor=COLOR_PRIMARY,
            darkcolor=COLOR_PRIMARY,
            thickness=14
        )
        self.style.configure(
            "Dark.Vertical.TScrollbar",
            troughcolor=COLOR_INPUT_BG,
            background=COLOR_CARD_BORDER,
            bordercolor=COLOR_BG,
            arrowcolor=COLOR_TEXT_MUTED
        )

    def setup_ui(self):
        # 1. Top Header Banner
        self.build_header()

        # 2. Segmented Pill Navigation Bar
        self.build_nav_tabs()

        # 3. Main Content Container
        self.content_container = tk.Frame(self.root, bg=COLOR_BG)
        self.content_container.pack(fill=tk.BOTH, expand=True, padx=16, pady=(0, 8))

        # Two main views (Receive and Send)
        self.tab_receive_frame = tk.Frame(self.content_container, bg=COLOR_BG)
        self.tab_send_frame = tk.Frame(self.content_container, bg=COLOR_BG)

        self.build_receive_tab()
        self.build_send_tab()

        # Default view: Receive Tab
        self.show_tab("receive")

        # 4. Modern Bottom Status Bar
        self.build_status_bar()

    def build_header(self):
        header_frame = tk.Frame(self.root, bg="#0e1524", height=60, bd=0)
        header_frame.pack(fill=tk.X, side=tk.TOP)

        # Left branding
        brand_frame = tk.Frame(header_frame, bg="#0e1524")
        brand_frame.pack(side=tk.LEFT, padx=18, pady=10)

        icon_label = tk.Label(
            brand_frame,
            text="⚡",
            font=("Segoe UI Emoji", 16, "bold"),
            bg="#0e1524",
            fg=COLOR_TEXT_ACCENT,
        )
        icon_label.pack(side=tk.LEFT, padx=(0, 8))

        title_box = tk.Frame(brand_frame, bg="#0e1524")
        title_box.pack(side=tk.LEFT)

        title_label = tk.Label(
            title_box,
            text="Python Socket File Transfer",
            font=("Segoe UI", 13, "bold"),
            bg="#0e1524",
            fg=COLOR_TEXT,
        )
        title_label.pack(anchor=tk.W)

        subtitle_label = tk.Label(
            title_box,
            text="High-Speed P2P Network Engine · SHA-256 Integrity Verified",
            font=("Segoe UI", 8),
            bg="#0e1524",
            fg=COLOR_TEXT_MUTED,
        )
        subtitle_label.pack(anchor=tk.W)

        # Right Live Engine Badge
        engine_badge = tk.Label(
            header_frame,
            text="● ENGINE READY",
            font=("Segoe UI", 9, "bold"),
            bg="#0d281e",
            fg=COLOR_SUCCESS,
            padx=12,
            pady=4,
            relief=tk.FLAT
        )
        engine_badge.pack(side=tk.RIGHT, padx=18, pady=14)

        # Subtle divider line
        divider = tk.Frame(self.root, bg=COLOR_CARD_BORDER, height=1)
        divider.pack(fill=tk.X)

    def build_nav_tabs(self):
        nav_container = tk.Frame(self.root, bg=COLOR_BG)
        nav_container.pack(fill=tk.X, padx=16, pady=12)

        # Segmented pill container
        pill_frame = tk.Frame(nav_container, bg=COLOR_CARD, bd=1, relief=tk.SOLID, highlightbackground=COLOR_CARD_BORDER, highlightthickness=1)
        pill_frame.pack(side=tk.LEFT)

        self.btn_nav_receive = tk.Button(
            pill_frame,
            text="  📥  Receive Files  (Server Mode)  ",
            font=("Segoe UI", 10, "bold"),
            bg=COLOR_PRIMARY,
            fg=COLOR_TEXT,
            relief=tk.FLAT,
            bd=0,
            padx=16,
            pady=8,
            cursor="hand2",
            command=lambda: self.show_tab("receive")
        )
        self.btn_nav_receive.pack(side=tk.LEFT, padx=3, pady=3)

        self.btn_nav_send = tk.Button(
            pill_frame,
            text="  📤  Send Files  (Client Mode)  ",
            font=("Segoe UI", 10, "bold"),
            bg=COLOR_CARD,
            fg=COLOR_TEXT_MUTED,
            relief=tk.FLAT,
            bd=0,
            padx=16,
            pady=8,
            cursor="hand2",
            command=lambda: self.show_tab("send")
        )
        self.btn_nav_send.pack(side=tk.LEFT, padx=3, pady=3)

    def show_tab(self, tab_name: str):
        if tab_name == "receive":
            self.tab_send_frame.pack_forget()
            self.tab_receive_frame.pack(fill=tk.BOTH, expand=True)
            self.btn_nav_receive.config(bg=COLOR_PRIMARY, fg=COLOR_TEXT)
            self.btn_nav_send.config(bg=COLOR_CARD, fg=COLOR_TEXT_MUTED)
        else:
            self.tab_receive_frame.pack_forget()
            self.tab_send_frame.pack(fill=tk.BOTH, expand=True)
            self.btn_nav_send.config(bg=COLOR_PRIMARY, fg=COLOR_TEXT)
            self.btn_nav_receive.config(bg=COLOR_CARD, fg=COLOR_TEXT_MUTED)

    def build_status_bar(self):
        status_frame = tk.Frame(self.root, bg="#080c14", bd=0, height=28)
        status_frame.pack(side=tk.BOTTOM, fill=tk.X)

        divider = tk.Frame(status_frame, bg=COLOR_CARD_BORDER, height=1)
        divider.pack(fill=tk.X, side=tk.TOP)

        self.status_bar = tk.Label(
            status_frame,
            text="● Ready. Choose Receive to listen or Send to transfer files.",
            font=("Segoe UI", 9),
            bg="#080c14",
            fg=COLOR_TEXT_MUTED,
            anchor=tk.W,
            padx=16,
            pady=5,
        )
        self.status_bar.pack(side=tk.LEFT, fill=tk.X)

    def _create_card(self, parent, title: str):
        """Creates a modern rounded card container with a title banner."""
        card = tk.Frame(parent, bg=COLOR_CARD, bd=1, relief=tk.SOLID, highlightbackground=COLOR_CARD_BORDER, highlightthickness=1)
        
        # Card header bar
        head = tk.Frame(card, bg=COLOR_CARD_HEADER, height=28)
        head.pack(fill=tk.X, side=tk.TOP)

        lbl = tk.Label(
            head,
            text=title,
            font=("Segoe UI", 9, "bold"),
            bg=COLOR_CARD_HEADER,
            fg=COLOR_TEXT_ACCENT,
            padx=12,
            pady=6,
        )
        lbl.pack(side=tk.LEFT)

        # Card content body
        body = tk.Frame(card, bg=COLOR_CARD, padx=14, pady=12)
        body.pack(fill=tk.BOTH, expand=True)
        return card, body

    # =========================================================================
    # TAB 1: RECEIVE TAB (SERVER)
    # =========================================================================
    def build_receive_tab(self):
        # Card 1: Server Settings
        card_settings, body_settings = self._create_card(self.tab_receive_frame, "⚙  SERVER CONFIGURATION")
        card_settings.pack(fill=tk.X, pady=(0, 10))

        # Port row
        row_port = tk.Frame(body_settings, bg=COLOR_CARD)
        row_port.pack(fill=tk.X, pady=(0, 8))

        lbl_port = tk.Label(row_port, text="Listen Port:", font=("Segoe UI", 9, "bold"), bg=COLOR_CARD, fg=COLOR_TEXT, width=14, anchor=tk.W)
        lbl_port.pack(side=tk.LEFT)

        self.recv_port_var = tk.StringVar(value=str(DEFAULT_PORT))
        self.recv_port_entry = tk.Entry(
            row_port,
            textvariable=self.recv_port_var,
            font=("Segoe UI", 9),
            bg=COLOR_INPUT_BG,
            fg=COLOR_TEXT,
            insertbackground=COLOR_TEXT_ACCENT,
            bd=1,
            relief=tk.FLAT,
            highlightbackground=COLOR_INPUT_BORDER,
            highlightcolor=COLOR_PRIMARY,
            highlightthickness=1,
            width=10,
        )
        self.recv_port_entry.pack(side=tk.LEFT, padx=(0, 12), ipady=3)

        # Save Folder row
        row_dir = tk.Frame(body_settings, bg=COLOR_CARD)
        row_dir.pack(fill=tk.X, pady=(0, 10))

        lbl_dir = tk.Label(row_dir, text="Save Folder:", font=("Segoe UI", 9, "bold"), bg=COLOR_CARD, fg=COLOR_TEXT, width=14, anchor=tk.W)
        lbl_dir.pack(side=tk.LEFT)

        default_dir = str(Path("received_files").resolve())
        self.save_dir_var = tk.StringVar(value=default_dir)
        self.save_dir_entry = tk.Entry(
            row_dir,
            textvariable=self.save_dir_var,
            font=("Segoe UI", 9),
            bg=COLOR_INPUT_BG,
            fg=COLOR_TEXT,
            insertbackground=COLOR_TEXT_ACCENT,
            bd=1,
            relief=tk.FLAT,
            highlightbackground=COLOR_INPUT_BORDER,
            highlightcolor=COLOR_PRIMARY,
            highlightthickness=1,
        )
        self.save_dir_entry.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 8), ipady=3)

        btn_browse = create_hover_button(row_dir, "Browse...", self.browse_save_dir, bg=COLOR_BTN_SEC, hover_bg=COLOR_BTN_SEC_HOVER)
        btn_browse.pack(side=tk.LEFT, padx=(0, 6))

        btn_open = create_hover_button(row_dir, "Open Folder ↗", self.open_save_dir, bg=COLOR_BTN_SEC, hover_bg=COLOR_BTN_SEC_HOVER)
        btn_open.pack(side=tk.LEFT)

        # Start/Stop Button & Status Badge Row
        row_ctrl = tk.Frame(body_settings, bg=COLOR_CARD)
        row_ctrl.pack(fill=tk.X, pady=(4, 0))

        self.btn_toggle_server = create_hover_button(
            row_ctrl,
            "▶  Start Receiver Server",
            self.toggle_server,
            bg=COLOR_SUCCESS,
            fg="#ffffff",
            hover_bg=COLOR_SUCCESS_HOVER,
            font=("Segoe UI", 10, "bold"),
            padx=18,
            pady=7
        )
        self.btn_toggle_server.pack(side=tk.LEFT)

        self.lbl_server_status = tk.Label(
            row_ctrl,
            text="⚪ Server Offline",
            font=("Segoe UI", 9, "bold"),
            bg="#182030",
            fg=COLOR_TEXT_MUTED,
            padx=12,
            pady=6,
            bd=0
        )
        self.lbl_server_status.pack(side=tk.LEFT, padx=12)

        # Card 2: How to Connect
        card_conn, body_conn = self._create_card(self.tab_receive_frame, "🌐  HOW TO CONNECT FROM SENDER DEVICE")
        card_conn.pack(fill=tk.X, pady=(0, 10))

        # Local IP Row
        row_local = tk.Frame(body_conn, bg=COLOR_CARD)
        row_local.pack(fill=tk.X, pady=(0, 8))

        lbl_l = tk.Label(row_local, text="Local Wi-Fi / LAN IP:", font=("Segoe UI", 9, "bold"), bg=COLOR_CARD, fg=COLOR_TEXT_MUTED, width=22, anchor=tk.W)
        lbl_l.pack(side=tk.LEFT)

        self.lbl_local_ip = tk.Label(
            row_local,
            text=f"{get_local_ip()}:{DEFAULT_PORT}",
            font=("Consolas", 10, "bold"),
            bg=COLOR_INPUT_BG,
            fg=COLOR_TEXT_ACCENT,
            padx=10,
            pady=4,
            relief=tk.FLAT,
            bd=1,
            highlightbackground=COLOR_INPUT_BORDER,
            highlightthickness=1
        )
        self.lbl_local_ip.pack(side=tk.LEFT, padx=(0, 8))

        btn_copy_ip = create_hover_button(row_local, "📋 Copy Local IP", self.copy_local_ip, bg=COLOR_BTN_SEC, hover_bg=COLOR_BTN_SEC_HOVER)
        btn_copy_ip.pack(side=tk.LEFT)

        # Global Pinggy Tunnel Row
        row_pinggy = tk.Frame(body_conn, bg=COLOR_CARD)
        row_pinggy.pack(fill=tk.X, pady=(4, 6))

        lbl_g = tk.Label(row_pinggy, text="Global Link (Assam ↔ Delhi):", font=("Segoe UI", 9, "bold"), bg=COLOR_CARD, fg=COLOR_TEXT_MUTED, width=22, anchor=tk.W)
        lbl_g.pack(side=tk.LEFT)

        self.btn_pinggy = create_hover_button(
            row_pinggy,
            "🌐 Generate Pinggy Global Link",
            self.toggle_pinggy_tunnel,
            bg=COLOR_PURPLE,
            fg="#ffffff",
            hover_bg=COLOR_PURPLE_HOVER,
            font=("Segoe UI", 9, "bold"),
            padx=14,
            pady=5
        )
        self.btn_pinggy.pack(side=tk.LEFT)

        # Pinggy URL entry box
        self.pinggy_url_entry = tk.Entry(
            body_conn,
            font=("Consolas", 9),
            bg=COLOR_INPUT_BG,
            fg="#c084fc",
            insertbackground="#c084fc",
            bd=1,
            relief=tk.FLAT,
            highlightbackground=COLOR_INPUT_BORDER,
            highlightthickness=1,
            state="readonly"
        )
        self.pinggy_url_entry.pack(fill=tk.X, pady=(2, 0), ipady=3)

        # Card 3: Activity Log
        card_log, body_log = self._create_card(self.tab_receive_frame, "📋  RECEIVER ACTIVITY LOG")
        card_log.pack(fill=tk.BOTH, expand=True)

        self.recv_log_text = tk.Text(
            body_log,
            height=7,
            wrap=tk.WORD,
            font=("Consolas", 9),
            bg="#050811",
            fg="#38bdf8",
            insertbackground="#38bdf8",
            bd=0,
            highlightthickness=1,
            highlightbackground=COLOR_CARD_BORDER,
            padx=8,
            pady=8
        )
        self.recv_log_text.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        recv_scrollbar = ttk.Scrollbar(body_log, orient=tk.VERTICAL, command=self.recv_log_text.yview, style="Dark.Vertical.TScrollbar")
        recv_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        self.recv_log_text.config(yscrollcommand=recv_scrollbar.set)

    # =========================================================================
    # TAB 2: SEND TAB (CLIENT)
    # =========================================================================
    def build_send_tab(self):
        # Card 1: Target Destination
        card_target, body_target = self._create_card(self.tab_send_frame, "🎯  RECEIVER DESTINATION")
        card_target.pack(fill=tk.X, pady=(0, 10))

        # Host entry row
        row_host = tk.Frame(body_target, bg=COLOR_CARD)
        row_host.pack(fill=tk.X, pady=(0, 8))

        lbl_host = tk.Label(row_host, text="Receiver IP / Link:", font=("Segoe UI", 9, "bold"), bg=COLOR_CARD, fg=COLOR_TEXT, width=18, anchor=tk.W)
        lbl_host.pack(side=tk.LEFT)

        self.send_host_var = tk.StringVar(value="127.0.0.1")
        self.send_host_entry = tk.Entry(
            row_host,
            textvariable=self.send_host_var,
            font=("Segoe UI", 9),
            bg=COLOR_INPUT_BG,
            fg=COLOR_TEXT,
            insertbackground=COLOR_TEXT_ACCENT,
            bd=1,
            relief=tk.FLAT,
            highlightbackground=COLOR_INPUT_BORDER,
            highlightcolor=COLOR_PRIMARY,
            highlightthickness=1
        )
        self.send_host_entry.pack(side=tk.LEFT, fill=tk.X, expand=True, ipady=3)
        self.send_host_entry.bind("<KeyRelease>", self.on_host_change)

        # Port entry row
        row_port = tk.Frame(body_target, bg=COLOR_CARD)
        row_port.pack(fill=tk.X)

        lbl_port = tk.Label(row_port, text="Receiver Port:", font=("Segoe UI", 9, "bold"), bg=COLOR_CARD, fg=COLOR_TEXT, width=18, anchor=tk.W)
        lbl_port.pack(side=tk.LEFT)

        self.send_port_var = tk.StringVar(value=str(DEFAULT_PORT))
        self.send_port_entry = tk.Entry(
            row_port,
            textvariable=self.send_port_var,
            font=("Segoe UI", 9),
            bg=COLOR_INPUT_BG,
            fg=COLOR_TEXT,
            insertbackground=COLOR_TEXT_ACCENT,
            bd=1,
            relief=tk.FLAT,
            highlightbackground=COLOR_INPUT_BORDER,
            highlightcolor=COLOR_PRIMARY,
            highlightthickness=1,
            width=10
        )
        self.send_port_entry.pack(side=tk.LEFT, ipady=3)

        lbl_auto = tk.Label(row_port, text="💡 Automatically auto-filled when you paste a Pinggy or ngrok URL", font=("Segoe UI", 8), bg=COLOR_CARD, fg=COLOR_TEXT_MUTED)
        lbl_auto.pack(side=tk.LEFT, padx=12)

        # Card 2: Files to Send
        card_files, body_files = self._create_card(self.tab_send_frame, "📁  FILES & FOLDERS QUEUE")
        card_files.pack(fill=tk.BOTH, expand=True, pady=(0, 10))

        # Action button toolbar
        toolbar = tk.Frame(body_files, bg=COLOR_CARD)
        toolbar.pack(fill=tk.X, pady=(0, 8))

        btn_add_files = create_hover_button(toolbar, "➕  Add File(s)...", self.add_files, bg=COLOR_BTN_SEC, hover_bg=COLOR_BTN_SEC_HOVER)
        btn_add_files.pack(side=tk.LEFT, padx=(0, 6))

        btn_add_dir = create_hover_button(toolbar, "📁  Add Entire Folder...", self.add_folder, bg=COLOR_BTN_SEC, hover_bg=COLOR_BTN_SEC_HOVER)
        btn_add_dir.pack(side=tk.LEFT, padx=(0, 6))

        btn_clear = create_hover_button(toolbar, "❌  Clear Queue", self.clear_send_list, bg="#2a1215", fg="#f87171", hover_bg="#3f171b")
        btn_clear.pack(side=tk.LEFT)

        # Listbox container
        list_container = tk.Frame(body_files, bg=COLOR_INPUT_BG, bd=1, relief=tk.SOLID, highlightbackground=COLOR_CARD_BORDER, highlightthickness=1)
        list_container.pack(fill=tk.BOTH, expand=True)

        self.send_listbox = tk.Listbox(
            list_container,
            selectmode=tk.EXTENDED,
            font=("Consolas", 9),
            bg=COLOR_INPUT_BG,
            fg=COLOR_TEXT,
            selectbackground=COLOR_PRIMARY,
            selectforeground="#ffffff",
            bd=0,
            highlightthickness=0,
            activestyle="none"
        )
        self.send_listbox.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=4, pady=4)

        list_scrollbar = ttk.Scrollbar(list_container, orient=tk.VERTICAL, command=self.send_listbox.yview, style="Dark.Vertical.TScrollbar")
        list_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        self.send_listbox.config(yscrollcommand=list_scrollbar.set)

        # Card 3: Transfer Progress & Execution
        card_prog, body_prog = self._create_card(self.tab_send_frame, "🚀  TRANSFER STATUS & CONTROL")
        card_prog.pack(fill=tk.X)

        self.progress_bar = ttk.Progressbar(body_prog, orient=tk.HORIZONTAL, mode="determinate", style="Dark.Horizontal.TProgressbar")
        self.progress_bar.pack(fill=tk.X, pady=(2, 6))

        self.lbl_send_stats = tk.Label(
            body_prog,
            text="Idle. Add files or folders above and click 'Start Transfer'.",
            font=("Segoe UI", 9),
            bg=COLOR_CARD,
            fg=COLOR_TEXT_MUTED,
            anchor=tk.W
        )
        self.lbl_send_stats.pack(fill=tk.X, pady=(0, 8))

        row_send_btn = tk.Frame(body_prog, bg=COLOR_CARD)
        row_send_btn.pack(fill=tk.X)

        self.btn_send_start = create_hover_button(
            row_send_btn,
            "🚀  START HIGH-SPEED TRANSFER NOW",
            self.start_send_transfer,
            bg=COLOR_PRIMARY,
            fg="#ffffff",
            hover_bg=COLOR_PRIMARY_HOVER,
            font=("Segoe UI", 10, "bold"),
            padx=24,
            pady=8
        )
        self.btn_send_start.pack(side=tk.LEFT)

    # =========================================================================
    # RECEIVER BACKEND LOGIC (PRESERVED 100%)
    # =========================================================================
    def browse_save_dir(self):
        chosen = filedialog.askdirectory(initialdir=self.save_dir_var.get())
        if chosen:
            self.save_dir_var.set(str(Path(chosen).resolve()))

    def open_save_dir(self):
        target_dir = Path(self.save_dir_var.get()).resolve()
        target_dir.mkdir(parents=True, exist_ok=True)
        if sys.platform == "win32":
            os.startfile(str(target_dir))
        elif sys.platform == "darwin":
            subprocess.run(["open", str(target_dir)])
        else:
            subprocess.run(["xdg-open", str(target_dir)])

    def copy_local_ip(self):
        self.root.clipboard_clear()
        self.root.clipboard_append(self.lbl_local_ip.cget("text"))
        messagebox.showinfo("Copied to Clipboard", f"Local IP copied:\n{self.lbl_local_ip.cget('text')}")

    def log_recv(self, msg: str):
        def _append():
            timestamp = time.strftime("[%H:%M:%S] ")
            self.recv_log_text.insert(tk.END, timestamp + msg + "\n")
            self.recv_log_text.see(tk.END)
        self.root.after(0, _append)

    def toggle_server(self):
        if not self.server_running:
            self.start_server()
        else:
            self.stop_server()

    def start_server(self):
        try:
            port = int(self.recv_port_var.get().strip())
        except ValueError:
            messagebox.showerror("Port Error", "Port must be a valid integer number (e.g. 5001)")
            return

        save_path = Path(self.save_dir_var.get()).resolve()
        save_path.mkdir(parents=True, exist_ok=True)

        self.listening_sockets = []
        # IPv4
        try:
            s4 = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            s4.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            s4.bind(("0.0.0.0", port))
            s4.listen(5)
            self.listening_sockets.append(s4)
        except Exception as e:
            messagebox.showerror("Socket Error", f"Could not bind to port {port}:\n{e}")
            return

        # IPv6 for localhost [::1] compatibility
        try:
            s6 = socket.socket(socket.AF_INET6, socket.SOCK_STREAM)
            s6.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            s6.bind(("::", port))
            s6.listen(5)
            self.listening_sockets.append(s6)
        except Exception:
            pass

        self.server_running = True
        self.btn_toggle_server.config(text="⏹  Stop Receiver", bg=COLOR_DANGER, activebackground=COLOR_DANGER_HOVER)
        self.btn_toggle_server._default_bg = COLOR_DANGER
        self.btn_toggle_server._hover_bg = COLOR_DANGER_HOVER

        self.lbl_server_status.config(
            text=f"🟢 Listening on Port {port} (IPv4+IPv6)",
            bg="#0d281e",
            fg=COLOR_SUCCESS
        )
        self.recv_port_entry.config(state="disabled")
        self.log_recv(f"Receiver started on Port {port}. Saving files to: {save_path}")

        # Update local IP label
        self.lbl_local_ip.config(text=f"{get_local_ip()}:{port}")
        self.status_bar.config(text=f"● Receiver online on Port {port}. Ready to accept connections.")

        self.server_thread = threading.Thread(target=self._server_loop, args=(save_path,), daemon=True)
        self.server_thread.start()

    def stop_server(self):
        self.server_running = False
        for s in self.listening_sockets:
            try:
                s.close()
            except Exception:
                pass
        self.listening_sockets = []

        self.btn_toggle_server.config(text="▶  Start Receiver Server", bg=COLOR_SUCCESS, activebackground=COLOR_SUCCESS_HOVER)
        self.btn_toggle_server._default_bg = COLOR_SUCCESS
        self.btn_toggle_server._hover_bg = COLOR_SUCCESS_HOVER

        self.lbl_server_status.config(text="⚪ Server Offline", bg="#182030", fg=COLOR_TEXT_MUTED)
        self.recv_port_entry.config(state="normal")
        self.log_recv("Receiver server stopped.")
        self.status_bar.config(text="● Receiver stopped.")

    def _server_loop(self, save_path: Path):
        while self.server_running:
            try:
                readable, _, _ = select.select(self.listening_sockets, [], [], 0.5)
                for s in readable:
                    if not self.server_running:
                        break
                    client_sock, client_addr = s.accept()
                    self.log_recv(f"Connected to sender at {client_addr[0]}:{client_addr[1]}")
                    self._handle_incoming_client(client_sock, client_addr, save_path)
            except Exception:
                break

    def _handle_incoming_client(self, client_sock: socket.socket, client_addr: tuple, save_dir: Path):
        def _worker():
            try:
                count = 0
                while self.server_running:
                    packet = recv_packet(client_sock)
                    action = packet.get("action", "TRANSFER_FILE")
                    if action == "SESSION_END":
                        self.log_recv(f"Session ended by sender {client_addr[0]}. Total files received: {count}")
                        break

                    filename = receiver.sanitize_filename(packet.get("filename", "unknown.bin"))
                    filesize = packet.get("filesize", 0)
                    expected_checksum = packet.get("checksum", "")
                    relative_path = packet.get("relative_path", "")

                    if relative_path:
                        parts = [p for p in Path(relative_path).parts if p not in ("..", "/", "\\", ".", "")]
                        if len(parts) > 1:
                            target_dir = save_dir.joinpath(*parts[:-1])
                            target_dir.mkdir(parents=True, exist_ok=True)
                            target_path = target_dir / filename
                        else:
                            target_path = receiver.get_unique_filepath(save_dir, filename)
                    else:
                        target_path = receiver.get_unique_filepath(save_dir, filename)

                    self.log_recv(f"Receiving '{filename}' ({format_bytes(filesize)})...")
                    send_packet(client_sock, {"status": "READY"})

                    hasher = hashlib.sha256()
                    bytes_received = 0
                    with open(target_path, "wb") as f:
                        while bytes_received < filesize:
                            chunk = client_sock.recv(min(CHUNK_SIZE, filesize - bytes_received))
                            if not chunk:
                                raise ConnectionError("Connection lost mid-transfer.")
                            f.write(chunk)
                            hasher.update(chunk)
                            bytes_received += len(chunk)

                    calc_hash = hasher.hexdigest()
                    if calc_hash.lower() == expected_checksum.lower():
                        self.log_recv(f"✔ File verified & saved: {target_path.name}")
                        send_packet(client_sock, {
                            "status": "SUCCESS",
                            "checksum_match": True,
                            "saved_to": str(target_path.resolve())
                        })
                        count += 1
                    else:
                        self.log_recv(f"✖ Checksum mismatch for {filename}!")
                        send_packet(client_sock, {"status": "ERROR", "checksum_match": False})
            except Exception as e:
                self.log_recv(f"Transfer error: {e}")
            finally:
                try:
                    client_sock.close()
                except Exception:
                    pass

        threading.Thread(target=_worker, daemon=True).start()

    # Pinggy Tunnel Generator
    def toggle_pinggy_tunnel(self):
        if self.pinggy_process:
            try:
                self.pinggy_process.terminate()
            except Exception:
                pass
            self.pinggy_process = None
            self.btn_pinggy.config(text="🌐 Generate Pinggy Global Link", bg=COLOR_PURPLE)
            self.btn_pinggy._default_bg = COLOR_PURPLE
            self.btn_pinggy._hover_bg = COLOR_PURPLE_HOVER
            self.set_pinggy_text("")
            self.log_recv("Pinggy public tunnel closed.")
            return

        # Automatically start the receiver server if not running!
        if not self.server_running:
            self.start_server()
            if not self.server_running:
                return

        port = self.recv_port_var.get().strip()
        cmd = ["ssh", "-p", "443", f"-R0:127.0.0.1:{port}", "tcp@a.pinggy.io"]

        self.btn_pinggy.config(text="⏳ Connecting Pinggy...", bg="#4c1d95")
        self.log_recv(f"Starting Pinggy SSH tunnel on port {port}...")

        def _pinggy_worker():
            try:
                self.pinggy_process = subprocess.Popen(
                    cmd,
                    stdin=subprocess.PIPE,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.STDOUT,
                    text=True,
                    bufsize=1,
                )
                for line in iter(self.pinggy_process.stdout.readline, ""):
                    if "tcp://" in line:
                        for token in line.split():
                            if token.startswith("tcp://"):
                                url = token.strip()
                                self.root.after(0, lambda u=url: self._on_pinggy_connected(u))
                                break
            except Exception as e:
                self.log_recv(f"Pinggy error: {e}")
                self.root.after(0, lambda: self.btn_pinggy.config(text="🌐 Generate Pinggy Global Link", bg=COLOR_PURPLE))

        threading.Thread(target=_pinggy_worker, daemon=True).start()

    def _on_pinggy_connected(self, url: str):
        self.pinggy_url = url
        self.set_pinggy_text(url)
        self.btn_pinggy.config(text="⏹ Stop Pinggy Tunnel", bg=COLOR_DANGER)
        self.btn_pinggy._default_bg = COLOR_DANGER
        self.btn_pinggy._hover_bg = COLOR_DANGER_HOVER
        self.log_recv(f"✔ Pinggy Public Link ready: {url}")
        messagebox.showinfo(
            "Global Public Link Ready!",
            f"Share this link with the sender in Delhi:\n\n{url}\n\n(Already copied to your clipboard!)"
        )
        self.root.clipboard_clear()
        self.root.clipboard_append(url)

    def set_pinggy_text(self, text: str):
        self.pinggy_url_entry.config(state="normal")
        self.pinggy_url_entry.delete(0, tk.END)
        self.pinggy_url_entry.insert(0, text)
        self.pinggy_url_entry.config(state="readonly")

    # =========================================================================
    # SENDER BACKEND LOGIC (PRESERVED 100%)
    # =========================================================================
    def on_host_change(self, event=None):
        val = self.send_host_var.get().strip()
        host, detected_port = sender.parse_host_port(val)
        if detected_port is not None:
            self.send_port_var.set(str(detected_port))

    def add_files(self):
        chosen_files = filedialog.askopenfilenames(title="Select File(s) to Send")
        if chosen_files:
            for f in chosen_files:
                p = Path(f).resolve()
                if p not in self.items_to_send:
                    self.items_to_send.append(p)
                    self.send_listbox.insert(tk.END, f"📄  {p.name}  ({format_bytes(p.stat().st_size)})  -  {p}")
            self.update_send_stats()

    def add_folder(self):
        chosen_dir = filedialog.askdirectory(title="Select Folder to Send")
        if chosen_dir:
            p = Path(chosen_dir).resolve()
            if p not in self.items_to_send:
                self.items_to_send.append(p)
                all_files = [f for f in p.rglob("*") if f.is_file()]
                total_sz = sum(f.stat().st_size for f in all_files)
                self.send_listbox.insert(tk.END, f"📁  {p.name}  [{len(all_files)} files, {format_bytes(total_sz)}]  -  {p}")
            self.update_send_stats()

    def clear_send_list(self):
        self.items_to_send = []
        self.send_listbox.delete(0, tk.END)
        self.progress_bar["value"] = 0
        self.lbl_send_stats.config(text="Queue cleared. Add files or folders above to begin.", fg=COLOR_TEXT_MUTED)

    def update_send_stats(self):
        total_items = len(self.items_to_send)
        self.lbl_send_stats.config(text=f"{total_items} item(s) queued for transmission.", fg=COLOR_TEXT)

    def start_send_transfer(self):
        if self.sender_running:
            return

        if not self.items_to_send:
            messagebox.showwarning("Empty Queue", "Please select at least one file or folder to send.")
            return

        raw_host = self.send_host_var.get().strip()
        host, detected_port = sender.parse_host_port(raw_host)
        try:
            port = int(self.send_port_var.get().strip()) if detected_port is None else detected_port
        except ValueError:
            messagebox.showerror("Port Error", "Port must be a valid number.")
            return

        self.sender_running = True
        self.btn_send_start.config(state="disabled", text="⏳  Transferring Files...", bg="#1d4ed8")

        def _send_worker():
            try:
                self._update_progress_ui(0, "Connecting to target receiver...")
                sock = socket.create_connection((host, port), timeout=25)
                sock.settimeout(None)

                total_files_transferred = 0
                for item_path in self.items_to_send:
                    if item_path.is_file():
                        success = self._send_single_file_gui(sock, item_path)
                        if success:
                            total_files_transferred += 1
                    elif item_path.is_dir():
                        all_files = [f for f in item_path.rglob("*") if f.is_file()]
                        for f in all_files:
                            rel = str(Path(item_path.name) / f.relative_to(item_path))
                            success = self._send_single_file_gui(sock, f, relative_path=rel)
                            if success:
                                total_files_transferred += 1

                try:
                    send_packet(sock, {"action": "SESSION_END"})
                except Exception:
                    pass
                sock.close()

                self.root.after(0, lambda: self._on_send_success(total_files_transferred))

            except Exception as e:
                self.root.after(0, lambda err=e: self._on_send_failure(err))
            finally:
                self.sender_running = False
                self.root.after(0, lambda: self.btn_send_start.config(
                    state="normal",
                    text="🚀  START HIGH-SPEED TRANSFER NOW",
                    bg=COLOR_PRIMARY
                ))

        threading.Thread(target=_send_worker, daemon=True).start()

    def _send_single_file_gui(self, sock: socket.socket, file_path: Path, relative_path: str = "") -> bool:
        filesize = file_path.stat().st_size
        filename = file_path.name

        self._update_progress_ui(0, f"Computing checksum for {filename}...")
        checksum = calculate_sha256(str(file_path))

        metadata = {
            "action": "TRANSFER_FILE",
            "filename": filename,
            "filesize": filesize,
            "checksum": checksum,
            "relative_path": relative_path,
        }
        send_packet(sock, metadata)

        ack = recv_packet(sock)
        if ack.get("status") != "READY":
            raise RuntimeError(f"Receiver rejected transfer: {ack.get('message')}")

        sent_bytes = 0
        start_time = time.time()
        last_update = start_time

        with open(file_path, "rb") as f:
            while sent_bytes < filesize:
                chunk = f.read(CHUNK_SIZE)
                if not chunk:
                    break
                sock.sendall(chunk)
                sent_bytes += len(chunk)

                now = time.time()
                if now - last_update >= 0.2 or sent_bytes >= filesize:
                    pct = (sent_bytes / max(filesize, 1)) * 100.0
                    elapsed = max(now - start_time, 0.001)
                    speed = sent_bytes / elapsed
                    eta = max((filesize - sent_bytes) / max(speed, 1), 0)
                    stat_str = f"Sending {filename}: {pct:.1f}% | {format_bytes(sent_bytes)}/{format_bytes(filesize)} | {format_bytes(speed)}/s | ETA: {int(eta)}s"
                    self._update_progress_ui(pct, stat_str)
                    last_update = now

        result = recv_packet(sock)
        return result.get("status") == "SUCCESS"

    def _update_progress_ui(self, pct: float, msg: str):
        def _cb():
            self.progress_bar["value"] = pct
            self.lbl_send_stats.config(text=msg, fg=COLOR_TEXT)
            self.status_bar.config(text=f"● {msg}")
        self.root.after(0, _cb)

    def _on_send_success(self, count: int):
        self.progress_bar["value"] = 100
        msg = f"✔ Transmission Succeeded! Transferred {count} file(s) with SHA-256 verification."
        self.lbl_send_stats.config(text=msg, fg=COLOR_SUCCESS)
        self.status_bar.config(text=f"● {msg}")
        messagebox.showinfo("Transfer Complete", msg)

    def _on_send_failure(self, err: Exception):
        msg = f"Transfer failed: {err}"
        self.lbl_send_stats.config(text=msg, fg=COLOR_DANGER)
        self.status_bar.config(text=f"● Error: {err}")
        messagebox.showerror("Transfer Error", msg)


def main():
    root = tk.Tk()
    app = FileTransferGUI(root)
    root.protocol("WM_DELETE_WINDOW", lambda: (app.stop_server(), root.destroy()))
    root.mainloop()


if __name__ == "__main__":
    main()

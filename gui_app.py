"""
gui_app.py - Modern Graphical User Interface for Python Socket File Transfer
Supports both Sending and Receiving in an intuitive, tabbed interface.
Works locally on LAN/Wi-Fi or globally across the internet (Pinggy/ngrok/Tailscale).
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

# Enable High DPI on Windows
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


class FileTransferGUI:
    def __init__(self, root: tk.Tk):
        self.root = root
        self.root.title("Python Socket File Transfer - GUI")
        self.root.geometry("780x640")
        self.root.minsize(700, 560)

        # Style configuration
        self.style = ttk.Style()
        try:
            self.style.theme_use("clam")
        except Exception:
            pass

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

    def setup_ui(self):
        # Header banner
        header_frame = tk.Frame(self.root, bg="#1e293b", height=50)
        header_frame.pack(fill=tk.X)
        header_label = tk.Label(
            header_frame,
            text="⚡ Python Socket File Transfer",
            font=("Segoe UI", 15, "bold"),
            bg="#1e293b",
            fg="#f8fafc",
            padx=15,
            pady=10,
        )
        header_label.pack(side=tk.LEFT)

        # Notebook tabs (Receive / Send)
        self.notebook = ttk.Notebook(self.root)
        self.notebook.pack(fill=tk.BOTH, expand=True, padx=12, pady=10)

        self.tab_receive = ttk.Frame(self.notebook)
        self.tab_send = ttk.Frame(self.notebook)

        self.notebook.add(self.tab_receive, text="  📥 Receive Files (Server)  ")
        self.notebook.add(self.tab_send, text="  📤 Send Files (Client)  ")

        self.build_receive_tab()
        self.build_send_tab()

        # Status Bar at bottom
        self.status_bar = tk.Label(
            self.root,
            text="Ready. Select Send or Receive to get started.",
            bd=1,
            relief=tk.SUNKEN,
            anchor=tk.W,
            font=("Segoe UI", 9),
            bg="#f1f5f9",
            padx=10,
            pady=3,
        )
        self.status_bar.pack(side=tk.BOTTOM, fill=tk.X)

    # =========================================================================
    # TAB 1: RECEIVE TAB
    # =========================================================================
    def build_receive_tab(self):
        frame = ttk.Frame(self.tab_receive, padding=12)
        frame.pack(fill=tk.BOTH, expand=True)

        # 1. Receiver Settings Frame
        settings_box = ttk.LabelFrame(frame, text=" Server Settings ", padding=10)
        settings_box.pack(fill=tk.X, pady=(0, 8))

        # Port Setting
        port_row = ttk.Frame(settings_box)
        port_row.pack(fill=tk.X, pady=3)
        ttk.Label(port_row, text="Listen Port:", width=15).pack(side=tk.LEFT)
        self.recv_port_var = tk.StringVar(value=str(DEFAULT_PORT))
        self.recv_port_entry = ttk.Entry(port_row, textvariable=self.recv_port_var, width=10)
        self.recv_port_entry.pack(side=tk.LEFT, padx=5)

        # Save Directory Setting
        dir_row = ttk.Frame(settings_box)
        dir_row.pack(fill=tk.X, pady=3)
        ttk.Label(dir_row, text="Save Folder:", width=15).pack(side=tk.LEFT)
        default_dir = str(Path("received_files").resolve())
        self.save_dir_var = tk.StringVar(value=default_dir)
        self.save_dir_entry = ttk.Entry(dir_row, textvariable=self.save_dir_var)
        self.save_dir_entry.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=5)
        ttk.Button(dir_row, text="Browse...", command=self.browse_save_dir).pack(side=tk.LEFT, padx=3)
        ttk.Button(dir_row, text="Open Folder", command=self.open_save_dir).pack(side=tk.LEFT)

        # 2. Control Buttons & Status Indicator
        ctrl_box = ttk.Frame(settings_box)
        ctrl_box.pack(fill=tk.X, pady=(8, 0))

        self.btn_toggle_server = tk.Button(
            ctrl_box,
            text="▶ Start Receiver",
            font=("Segoe UI", 10, "bold"),
            bg="#16a34a",
            fg="white",
            padx=15,
            pady=4,
            command=self.toggle_server,
        )
        self.btn_toggle_server.pack(side=tk.LEFT)

        self.lbl_server_status = tk.Label(
            ctrl_box,
            text="⚪ Status: Stopped",
            font=("Segoe UI", 10, "bold"),
            fg="#64748b",
            padx=12,
        )
        self.lbl_server_status.pack(side=tk.LEFT)

        # 3. Connection Address Box
        addr_box = ttk.LabelFrame(frame, text=" How to Connect From Sender ", padding=10)
        addr_box.pack(fill=tk.X, pady=6)

        # Local IP
        local_row = ttk.Frame(addr_box)
        local_row.pack(fill=tk.X, pady=2)
        ttk.Label(local_row, text="Local Network IP (Same Wi-Fi):", font=("Segoe UI", 9, "bold")).pack(side=tk.LEFT)
        self.lbl_local_ip = ttk.Label(local_row, text=f"{get_local_ip()}:{DEFAULT_PORT}", foreground="#0284c7")
        self.lbl_local_ip.pack(side=tk.LEFT, padx=10)
        ttk.Button(local_row, text="📋 Copy", command=self.copy_local_ip).pack(side=tk.LEFT)

        # Global Pinggy Link
        tunnel_row = ttk.Frame(addr_box)
        tunnel_row.pack(fill=tk.X, pady=(6, 2))
        ttk.Label(tunnel_row, text="Global Internet Link (Assam ↔ Delhi):", font=("Segoe UI", 9, "bold")).pack(side=tk.LEFT)
        self.btn_pinggy = ttk.Button(tunnel_row, text="🌐 Generate Pinggy Link", command=self.toggle_pinggy_tunnel)
        self.btn_pinggy.pack(side=tk.LEFT, padx=10)

        self.pinggy_url_entry = ttk.Entry(addr_box, state="readonly")
        self.pinggy_url_entry.pack(fill=tk.X, pady=(4, 0))

        # 4. Received Files Log
        log_box = ttk.LabelFrame(frame, text=" Activity Log ", padding=8)
        log_box.pack(fill=tk.BOTH, expand=True, pady=(6, 0))

        self.recv_log_text = tk.Text(log_box, height=8, wrap=tk.WORD, font=("Consolas", 9), bg="#0f172a", fg="#f8fafc")
        self.recv_log_text.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        recv_scrollbar = ttk.Scrollbar(log_box, orient=tk.VERTICAL, command=self.recv_log_text.yview)
        recv_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        self.recv_log_text.config(yscrollcommand=recv_scrollbar.set)

    # =========================================================================
    # TAB 2: SEND TAB
    # =========================================================================
    def build_send_tab(self):
        frame = ttk.Frame(self.tab_send, padding=12)
        frame.pack(fill=tk.BOTH, expand=True)

        # 1. Receiver Target Frame
        target_box = ttk.LabelFrame(frame, text=" Receiver Destination ", padding=10)
        target_box.pack(fill=tk.X, pady=(0, 8))

        row1 = ttk.Frame(target_box)
        row1.pack(fill=tk.X, pady=3)
        ttk.Label(row1, text="Receiver IP / Link:", width=18).pack(side=tk.LEFT)
        self.send_host_var = tk.StringVar(value="127.0.0.1")
        self.send_host_entry = ttk.Entry(row1, textvariable=self.send_host_var)
        self.send_host_entry.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=5)
        self.send_host_entry.bind("<KeyRelease>", self.on_host_change)

        row2 = ttk.Frame(target_box)
        row2.pack(fill=tk.X, pady=3)
        ttk.Label(row2, text="Receiver Port:", width=18).pack(side=tk.LEFT)
        self.send_port_var = tk.StringVar(value=str(DEFAULT_PORT))
        self.send_port_entry = ttk.Entry(row2, textvariable=self.send_port_var, width=10)
        self.send_port_entry.pack(side=tk.LEFT, padx=5)
        ttk.Label(row2, text="(Auto-detected if you paste full Pinggy or ngrok link)", font=("Segoe UI", 8), foreground="#64748b").pack(side=tk.LEFT, padx=10)

        # 2. Files Selection Frame
        files_box = ttk.LabelFrame(frame, text=" Files to Send ", padding=10)
        files_box.pack(fill=tk.BOTH, expand=True, pady=(0, 8))

        btn_row = ttk.Frame(files_box)
        btn_row.pack(fill=tk.X, pady=(0, 6))
        ttk.Button(btn_row, text="➕ Add File(s)...", command=self.add_files).pack(side=tk.LEFT, padx=(0, 5))
        ttk.Button(btn_row, text="📁 Add Folder...", command=self.add_folder).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_row, text="❌ Clear List", command=self.clear_send_list).pack(side=tk.LEFT, padx=5)

        # Listbox for files to send
        list_container = ttk.Frame(files_box)
        list_container.pack(fill=tk.BOTH, expand=True)
        self.send_listbox = tk.Listbox(list_container, selectmode=tk.EXTENDED, font=("Consolas", 9), bg="#ffffff")
        self.send_listbox.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        list_scrollbar = ttk.Scrollbar(list_container, orient=tk.VERTICAL, command=self.send_listbox.yview)
        list_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        self.send_listbox.config(yscrollcommand=list_scrollbar.set)

        # 3. Transfer Progress & Action Frame
        action_box = ttk.LabelFrame(frame, text=" Transfer Progress ", padding=10)
        action_box.pack(fill=tk.X)

        self.progress_bar = ttk.Progressbar(action_box, orient=tk.HORIZONTAL, mode="determinate")
        self.progress_bar.pack(fill=tk.X, pady=4)

        self.lbl_send_stats = tk.Label(
            action_box,
            text="Idle - Select files and click Send.",
            font=("Segoe UI", 9),
            anchor=tk.W,
            fg="#334155",
        )
        self.lbl_send_stats.pack(fill=tk.X, pady=2)

        action_btn_row = ttk.Frame(action_box)
        action_btn_row.pack(fill=tk.X, pady=(6, 0))

        self.btn_send_start = tk.Button(
            action_btn_row,
            text="🚀 Send Files Now",
            font=("Segoe UI", 10, "bold"),
            bg="#2563eb",
            fg="white",
            padx=20,
            pady=5,
            command=self.start_send_transfer,
        )
        self.btn_send_start.pack(side=tk.LEFT)

    # =========================================================================
    # RECEIVER LOGIC
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
        messagebox.showinfo("Copied", f"Copied to clipboard:\n{self.lbl_local_ip.cget('text')}")

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
            messagebox.showerror("Error", "Port must be a valid number (e.g. 5001)")
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
            messagebox.showerror("Error", f"Could not bind to port {port}: {e}")
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
        self.btn_toggle_server.config(text="⏹ Stop Receiver", bg="#dc2626")
        self.lbl_server_status.config(text=f"🟢 Listening on Port {port}", fg="#16a34a")
        self.recv_port_entry.config(state="disabled")
        self.log_recv(f"Receiver started on Port {port}. Saving to: {save_path}")

        # Update local IP label
        self.lbl_local_ip.config(text=f"{get_local_ip()}:{port}")

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
        self.btn_toggle_server.config(text="▶ Start Receiver", bg="#16a34a")
        self.lbl_server_status.config(text="⚪ Status: Stopped", fg="#64748b")
        self.recv_port_entry.config(state="normal")
        self.log_recv("Receiver server stopped.")

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
                        self.log_recv(f"Session ended by sender {client_addr[0]}. Total files: {count}")
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
                        self.log_recv(f"✔ File saved & verified: {target_path.name}")
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
            self.btn_pinggy.config(text="🌐 Generate Pinggy Link")
            self.set_pinggy_text("")
            self.log_recv("Pinggy public tunnel closed.")
            return

        # Automatically start the receiver server if not running!
        if not self.server_running:
            self.start_server()
            if not self.server_running:
                # Failed to start receiver (e.g. port error)
                return

        port = self.recv_port_var.get().strip()
        cmd = ["ssh", "-p", "443", f"-R0:127.0.0.1:{port}", "tcp@a.pinggy.io"]

        self.btn_pinggy.config(text="⏳ Connecting Pinggy...")
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
                self.root.after(0, lambda: self.btn_pinggy.config(text="🌐 Generate Pinggy Link"))

        threading.Thread(target=_pinggy_worker, daemon=True).start()

    def _on_pinggy_connected(self, url: str):
        self.pinggy_url = url
        self.set_pinggy_text(url)
        self.btn_pinggy.config(text="⏹ Stop Pinggy")
        self.log_recv(f"✔ Pinggy Public Link ready: {url}")
        messagebox.showinfo(
            "Global Link Generated!",
            f"Share this address with the sender in Delhi:\n\n{url}\n\n(Copied to your clipboard!)"
        )
        self.root.clipboard_clear()
        self.root.clipboard_append(url)

    def set_pinggy_text(self, text: str):
        self.pinggy_url_entry.config(state="normal")
        self.pinggy_url_entry.delete(0, tk.END)
        self.pinggy_url_entry.insert(0, text)
        self.pinggy_url_entry.config(state="readonly")

    # =========================================================================
    # SENDER LOGIC
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
                    self.send_listbox.insert(tk.END, f"📄 {p.name} ({format_bytes(p.stat().st_size)}) - {p}")
            self.update_send_stats()

    def add_folder(self):
        chosen_dir = filedialog.askdirectory(title="Select Folder to Send")
        if chosen_dir:
            p = Path(chosen_dir).resolve()
            if p not in self.items_to_send:
                self.items_to_send.append(p)
                all_files = [f for f in p.rglob("*") if f.is_file()]
                total_sz = sum(f.stat().st_size for f in all_files)
                self.send_listbox.insert(tk.END, f"📁 {p.name} [{len(all_files)} files, {format_bytes(total_sz)}] - {p}")
            self.update_send_stats()

    def clear_send_list(self):
        self.items_to_send = []
        self.send_listbox.delete(0, tk.END)
        self.progress_bar["value"] = 0
        self.lbl_send_stats.config(text="List cleared. Add files to send.")

    def update_send_stats(self):
        total_items = len(self.items_to_send)
        self.lbl_send_stats.config(text=f"{total_items} item(s) queued for transfer.")

    def start_send_transfer(self):
        if self.sender_running:
            return

        if not self.items_to_send:
            messagebox.showwarning("No Files", "Please add at least one file or folder to send.")
            return

        raw_host = self.send_host_var.get().strip()
        host, detected_port = sender.parse_host_port(raw_host)
        try:
            port = int(self.send_port_var.get().strip()) if detected_port is None else detected_port
        except ValueError:
            messagebox.showerror("Error", "Port must be a valid number.")
            return

        self.sender_running = True
        self.btn_send_start.config(state="disabled", text="⏳ Sending...")

        def _send_worker():
            try:
                self._update_progress_ui(0, "Connecting to receiver...")
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
                self.root.after(0, lambda: self.btn_send_start.config(state="normal", text="🚀 Send Files Now"))

        threading.Thread(target=_send_worker, daemon=True).start()

    def _send_single_file_gui(self, sock: socket.socket, file_path: Path, relative_path: str = "") -> bool:
        filesize = file_path.stat().st_size
        filename = file_path.name

        self._update_progress_ui(0, f"Hashing {filename}...")
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
            raise RuntimeError(f"Receiver rejected: {ack.get('message')}")

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
            self.lbl_send_stats.config(text=msg)
            self.status_bar.config(text=msg)
        self.root.after(0, _cb)

    def _on_send_success(self, count: int):
        self.progress_bar["value"] = 100
        msg = f"✔ Transfer Complete! Successfully sent {count} file(s)."
        self.lbl_send_stats.config(text=msg, fg="#16a34a")
        self.status_bar.config(text=msg)
        messagebox.showinfo("Success", msg)

    def _on_send_failure(self, err: Exception):
        msg = f"Transfer failed: {err}"
        self.lbl_send_stats.config(text=msg, fg="#dc2626")
        self.status_bar.config(text=msg)
        messagebox.showerror("Transfer Error", msg)


def main():
    root = tk.Tk()
    app = FileTransferGUI(root)
    root.protocol("WM_DELETE_WINDOW", lambda: (app.stop_server(), root.destroy()))
    root.mainloop()


if __name__ == "__main__":
    main()

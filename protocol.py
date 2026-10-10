"""
protocol.py - Core networking protocol and helper utilities
for Python Socket File Transfer Application.
"""

import os
import sys
import json
import struct
import socket
import hashlib
import time
from pathlib import Path

# Protocol Constants
MAGIC_HEADER = b"FTXFER1"  # 7-byte protocol identifier
HEADER_PREFIX_FORMAT = "!7sI"  # Magic (7 bytes) + Header JSON Length (4 bytes unsigned int)
HEADER_PREFIX_SIZE = struct.calcsize(HEADER_PREFIX_FORMAT)
DEFAULT_PORT = 5001
DEFAULT_BUFFER_SIZE = 64 * 1024  # 64 KB chunks
CHUNK_SIZE = 64 * 1024


def get_local_ip() -> str:
    """
    Detect the outbound local IP address of this device on the local network (LAN / Wi-Fi).
    """
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        # Connecting to a public address (doesn't actually send packets)
        # to determine which network interface the OS chooses.
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
    except Exception:
        ip = "127.0.0.1"
    finally:
        s.close()
    return ip


def get_all_ips() -> list:
    """
    Get all host IP addresses associated with this device.
    """
    ips = set()
    try:
        local_primary = get_local_ip()
        if local_primary != "127.0.0.1":
            ips.add(local_primary)
        hostname = socket.gethostname()
        for ip in socket.gethostbyname_ex(hostname)[2]:
            if not ip.startswith("127."):
                ips.add(ip)
    except Exception:
        pass
    if not ips:
        ips.add("127.0.0.1")
    return sorted(list(ips))


def calculate_sha256(filepath: str, callback=None) -> str:
    """
    Calculate the SHA-256 checksum of a file.
    """
    sha256 = hashlib.sha256()
    with open(filepath, "rb") as f:
        while chunk := f.read(CHUNK_SIZE):
            sha256.update(chunk)
            if callback:
                callback(len(chunk))
    return sha256.hexdigest()


def send_exact(sock: socket.socket, data: bytes) -> None:
    """
    Send all bytes through the socket.
    """
    sock.sendall(data)


def recv_exact(sock: socket.socket, size: int) -> bytes:
    """
    Receive exactly `size` bytes from the socket.
    Raises ConnectionError if the socket closes early.
    """
    buffer = bytearray()
    while len(buffer) < size:
        chunk = sock.recv(size - len(buffer))
        if not chunk:
            raise ConnectionError(f"Connection closed prematurely. Received {len(buffer)} of {size} bytes.")
        buffer.extend(chunk)
    return bytes(buffer)


def send_packet(sock: socket.socket, data_dict: dict) -> None:
    """
    Pack and send a JSON metadata packet with magic header and length prefix.
    """
    raw_json = json.dumps(data_dict).encode("utf-8")
    header = struct.pack(HEADER_PREFIX_FORMAT, MAGIC_HEADER, len(raw_json))
    send_exact(sock, header + raw_json)


def recv_packet(sock: socket.socket) -> dict:
    """
    Receive and unpack a JSON metadata packet.
    """
    header_bytes = recv_exact(sock, HEADER_PREFIX_SIZE)
    magic, json_len = struct.unpack(HEADER_PREFIX_FORMAT, header_bytes)
    if magic != MAGIC_HEADER:
        # Try to read extra buffered text (e.g., if a tunnel like ngrok sent an error string)
        extra_text = bytearray(header_bytes)
        sock.settimeout(0.5)
        try:
            while len(extra_text) < 512:
                chunk = sock.recv(512)
                if not chunk:
                    break
                extra_text.extend(chunk)
        except Exception:
            pass
        sock.settimeout(None)

        decoded_error = extra_text.decode("utf-8", errors="replace").strip()
        if "ngrok" in decoded_error.lower() or "banned" in decoded_error.lower():
            raise ConnectionError(f"Tunnel Error from ngrok:\n>>> {decoded_error}")
        
        raise ValueError(f"Invalid protocol header (received {repr(header_bytes[:16])}, expected {MAGIC_HEADER!r}). Raw message: {decoded_error[:100]}")
    
    raw_json = recv_exact(sock, json_len)
    return json.loads(raw_json.decode("utf-8"))


def format_bytes(size: float) -> str:
    """
    Format byte count into human-readable string (B, KB, MB, GB).
    """
    for unit in ["B", "KB", "MB", "GB", "TB"]:
        if size < 1024.0:
            return f"{size:.2f} {unit}"
        size /= 1024.0
    return f"{size:.2f} PB"


class ProgressBar:
    """
    Terminal progress bar displaying transfer status, percentage, speed, and ETA.
    """
    def __init__(self, total_bytes: int, title: str = "Transferring", width: int = 30):
        self.total_bytes = max(total_bytes, 1)
        self.transferred = 0
        self.title = title
        self.width = width
        self.start_time = time.time()
        self.last_update_time = self.start_time
        self.last_bytes = 0
        self.speed = 0.0

    def update(self, chunk_size: int):
        self.transferred += chunk_size
        now = time.time()
        elapsed_since_last = now - self.last_update_time
        
        # Recalculate speed every 0.25 seconds or at completion
        if elapsed_since_last >= 0.25 or self.transferred >= self.total_bytes:
            bytes_diff = self.transferred - self.last_bytes
            if elapsed_since_last > 0:
                self.speed = bytes_diff / elapsed_since_last
            self.last_update_time = now
            self.last_bytes = self.transferred
            self.render()

    def render(self):
        fraction = min(self.transferred / self.total_bytes, 1.0)
        filled = int(self.width * fraction)
        bar = "█" * filled + "░" * (self.width - filled)
        percent = fraction * 100.0

        elapsed_total = time.time() - self.start_time
        overall_speed = self.transferred / max(elapsed_total, 0.001)
        display_speed = self.speed if self.speed > 0 else overall_speed

        remaining_bytes = max(self.total_bytes - self.transferred, 0)
        eta_seconds = int(remaining_bytes / display_speed) if display_speed > 0 else 0
        eta_str = f"{eta_seconds // 60:02d}:{eta_seconds % 60:02d}"

        info_transferred = format_bytes(self.transferred)
        info_total = format_bytes(self.total_bytes)
        info_speed = format_bytes(display_speed) + "/s"

        sys.stdout.write(
            f"\r{self.title}: [{bar}] {percent:5.1f}% | {info_transferred}/{info_total} | {info_speed} | ETA: {eta_str} "
        )
        sys.stdout.flush()

    def finish(self, message: str = "Completed!"):
        self.render()
        sys.stdout.write("\n")
        total_time = max(time.time() - self.start_time, 0.001)
        avg_speed = format_bytes(self.transferred / total_time) + "/s"
        print(f"[*] {message} Time: {total_time:.2f}s (Avg Speed: {avg_speed})")

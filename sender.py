"""
sender.py - Socket File Transfer Sender (Client)
Connects to receiver on another device and sends files or folders.
"""

import os
import sys
import socket
import argparse
from pathlib import Path

from protocol import (
    DEFAULT_PORT,
    CHUNK_SIZE,
    calculate_sha256,
    send_packet,
    recv_packet,
    format_bytes,
    ProgressBar,
)


def clean_input_path(path_str: str) -> str:
    """
    Clean input string by stripping surrounding quotes (often added when
    files are dragged-and-dropped into terminal).
    """
    path_str = path_str.strip()
    if (path_str.startswith('"') and path_str.endswith('"')) or (
        path_str.startswith("'") and path_str.endswith("'")
    ):
        path_str = path_str[1:-1]
    return path_str.strip()


def send_file(sock: socket.socket, file_path: Path, relative_path: str = "") -> bool:
    """
    Send a single file over the established socket connection.
    """
    if not file_path.is_file():
        print(f"[!] Path is not a valid file: {file_path}")
        return False

    filesize = file_path.stat().st_size
    filename = file_path.name

    print(f"\n[+] Preparing: '{filename}'")
    print(f"    Size: {format_bytes(filesize)} ({filesize:,} bytes)")
    print(f"    Calculating SHA-256 checksum...")

    checksum = calculate_sha256(str(file_path))
    print(f"    SHA-256: {checksum[:16]}...")

    # 1. Send handshake metadata packet
    metadata = {
        "action": "TRANSFER_FILE",
        "filename": filename,
        "filesize": filesize,
        "checksum": checksum,
        "relative_path": relative_path,
    }
    
    try:
        send_packet(sock, metadata)
    except Exception as e:
        print(f"[!] Failed to send metadata packet: {e}")
        return False

    # 2. Wait for receiver ready acknowledgment
    try:
        ack = recv_packet(sock)
        if ack.get("status") != "READY":
            print(f"[!] Receiver rejected transfer: {ack.get('message')}")
            return False
    except Exception as e:
        print(f"[!] Did not receive ready acknowledgment from receiver: {e}")
        return False

    # 3. Stream file chunks
    progress = ProgressBar(filesize, title=f"Uploading {filename}")
    bytes_sent = 0

    try:
        with open(file_path, "rb") as f:
            while bytes_sent < filesize:
                chunk = f.read(CHUNK_SIZE)
                if not chunk:
                    break
                sock.sendall(chunk)
                bytes_sent += len(chunk)
                progress.update(len(chunk))

        progress.finish("File transmission complete.")
    except Exception as e:
        sys.stdout.write("\n")
        print(f"[!] Error while streaming file data: {e}")
        return False

    # 4. Wait for receiver verification confirmation
    try:
        result = recv_packet(sock)
        if result.get("status") == "SUCCESS" and result.get("checksum_match"):
            saved_to = result.get("saved_to", "")
            print(f"[✔] File verified and saved successfully by receiver!")
            if saved_to:
                print(f"    Saved destination on receiver: {saved_to}\n")
            else:
                print()
            return True
        else:
            print(f"[✖] Receiver reported verification error: {result.get('message', 'Checksum mismatch')}\n")
            return False
    except Exception as e:
        print(f"[!] Error receiving transfer confirmation: {e}\n")
        return False


def send_folder(sock: socket.socket, folder_path: Path) -> int:
    """
    Recursively send all files in a folder preserving relative directory structure.
    """
    if not folder_path.is_dir():
        print(f"[!] Path is not a valid folder: {folder_path}")
        return 0

    all_files = [p for p in folder_path.rglob("*") if p.is_file()]
    if not all_files:
        print(f"[!] Folder is empty: {folder_path}")
        return 0

    total_bytes = sum(f.stat().st_size for f in all_files)
    print(f"\n[*] Found {len(all_files)} files in folder '{folder_path.name}' (Total: {format_bytes(total_bytes)})")

    success_count = 0
    for idx, file_item in enumerate(all_files, start=1):
        rel_path = str(Path(folder_path.name) / file_item.relative_to(folder_path))
        print(f"\n--- [{idx}/{len(all_files)}] Sending: {rel_path} ---")
        if send_file(sock, file_item, relative_path=rel_path):
            success_count += 1
        else:
            print(f"[!] Failed to transfer: {rel_path}")

    return success_count


def run_sender(host: str, port: int, items_to_send: list):
    """
    Connect to receiver and transmit files/folders.
    """
    print("=" * 60)
    print("            PYTHON SOCKET FILE SENDER (CLIENT)            ")
    print("=" * 60)
    print(f"[*] Target Receiver: {host}:{port}")

    try:
        print(f"[*] Connecting to receiver at {host}:{port}...")
        # socket.create_connection automatically handles domain names (e.g. ngrok), IPv4, and IPv6
        sock = socket.create_connection((host, port), timeout=30)
        sock.settimeout(None)  # Reset to blocking mode for data transfer
        print("[+] Connected successfully!\n")
    except socket.timeout:
        print(f"[!] Connection timed out trying to reach {host}:{port}.")
        print("    Please verify the receiver is running and Firewall allows port", port)
        return
    except Exception as e:
        print(f"[!] Could not connect to {host}:{port} - {e}")
        print("    Check that the IP and Port are correct and both devices are on the same network.")
        return

    transferred = 0
    try:
        for item_str in items_to_send:
            item_path = Path(clean_input_path(item_str)).resolve()
            if not item_path.exists():
                print(f"[!] File or folder does not exist: {item_path}")
                continue

            if item_path.is_dir():
                transferred += send_folder(sock, item_path)
            elif item_path.is_file():
                if send_file(sock, item_path):
                    transferred += 1

        # Send session end packet
        try:
            send_packet(sock, {"action": "SESSION_END"})
        except Exception:
            pass

    finally:
        sock.close()

    print("=" * 60)
    print(f"[✔] Session finished. Successfully transferred {transferred} file(s).")
    print("=" * 60)


def parse_host_port(host_str: str, default_port: int = DEFAULT_PORT):
    """
    Intelligently parse host and port from various formats, such as:
    - tcp://0.tcp.in.ngrok.io:10744
    - 0.tcp.in.ngrok.io:10744
    - 192.168.1.15:5001
    - 192.168.1.15
    """
    host_str = host_str.strip()
    # Strip protocols if user pasted from ngrok
    if host_str.startswith("tcp://"):
        host_str = host_str[len("tcp://"):]
    elif host_str.startswith("http://"):
        host_str = host_str[len("http://"):]

    if ":" in host_str:
        parts = host_str.split(":", 1)
        host = parts[0].strip()
        try:
            port = int(parts[1].strip())
            return host, port
        except ValueError:
            return host, default_port
    return host_str, None


def interactive_mode():
    """
    Interactive terminal prompt for entering receiver IP and files.
    """
    print("=" * 60)
    print("            PYTHON SOCKET FILE SENDER (CLIENT)            ")
    print("=" * 60)

    # 1. Receiver Host
    default_host = "127.0.0.1"
    host_input = input(
        f"Enter Receiver IP / ngrok URL [e.g. 0.tcp.in.ngrok.io:10744 or press Enter for {default_host}]: "
    ).strip()

    if not host_input:
        host = default_host
        detected_port = None
    else:
        host, detected_port = parse_host_port(host_input)

    # 2. Receiver Port
    if detected_port is not None:
        print(f"[*] Detected Port from URL: {detected_port}")
        port = detected_port
    else:
        port_input = input(f"Enter Port [press Enter for {DEFAULT_PORT}]: ").strip()
        try:
            port = int(port_input) if port_input else DEFAULT_PORT
        except ValueError:
            print(f"[!] Invalid port, using default: {DEFAULT_PORT}")
            port = DEFAULT_PORT

    # 3. File or Folder Path
    while True:
        target_path_input = input("\nEnter path to file or folder to send (or drag & drop here): ").strip()
        cleaned_path = clean_input_path(target_path_input)
        if not cleaned_path:
            print("[!] Path cannot be empty.")
            continue
        
        target_path = Path(cleaned_path).resolve()
        if not target_path.exists():
            print(f"[!] '{target_path}' not found! Please check path.")
            continue
        break

    run_sender(host, port, [cleaned_path])


def main():
    parser = argparse.ArgumentParser(description="Python Socket File Transfer - Sender")
    parser.add_argument("--host", "-H", type=str, help="Receiver IP address")
    parser.add_argument("--port", "-p", type=int, default=DEFAULT_PORT, help=f"Port (default: {DEFAULT_PORT})")
    parser.add_argument("--file", "-f", action="append", help="File or folder path to send (can specify multiple)")

    args = parser.parse_args()

    # If arguments were provided via CLI, run CLI mode; otherwise run interactive mode
    if args.host and args.file:
        run_sender(args.host, args.port, args.file)
    else:
        interactive_mode()


if __name__ == "__main__":
    main()

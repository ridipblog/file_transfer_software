"""
receiver.py - Socket File Transfer Receiver (Server)
Listens for incoming file transfers from another device.
"""

import os
import sys
import socket
import select
import argparse
import hashlib
from pathlib import Path

from protocol import (
    DEFAULT_PORT,
    CHUNK_SIZE,
    get_all_ips,
    recv_packet,
    send_packet,
    format_bytes,
    calculate_sha256,
    ProgressBar,
)


def sanitize_filename(filename: str) -> str:
    """
    Sanitize filename to prevent directory traversal and invalid path characters.
    """
    clean_name = os.path.basename(filename.replace("\\", "/"))
    # Disallow empty or dangerous filenames
    if not clean_name or clean_name in (".", ".."):
        clean_name = "unnamed_file.bin"
    return clean_name


def get_unique_filepath(save_dir: Path, filename: str) -> Path:
    """
    If a file with the same name already exists, append (1), (2), etc.
    """
    target = save_dir / filename
    if not target.exists():
        return target

    stem = target.stem
    suffix = target.suffix
    counter = 1
    while True:
        candidate = save_dir / f"{stem} ({counter}){suffix}"
        if not candidate.exists():
            return candidate
        counter += 1


def receive_single_file(client_sock: socket.socket, save_dir: Path, client_addr: tuple) -> bool:
    """
    Receive one file from the connected client socket.
    Returns True if more files may follow, or False if transfer finished.
    """
    # 1. Wait for file metadata packet or session control packet
    try:
        packet = recv_packet(client_sock)
    except ConnectionError:
        print(f"[*] Client {client_addr[0]}:{client_addr[1]} disconnected.")
        return False
    except Exception as e:
        print(f"[!] Error receiving handshake metadata: {e}")
        return False

    action = packet.get("action", "TRANSFER_FILE")
    if action == "SESSION_END":
        print("[*] Sender indicated transfer session is finished.")
        return False

    original_filename = packet.get("filename", "unknown.bin")
    filesize = packet.get("filesize", 0)
    expected_checksum = packet.get("checksum", "")
    relative_path = packet.get("relative_path", "")

    # Clean the filename & handle subfolders if relative_path is provided
    clean_name = sanitize_filename(original_filename)

    if relative_path:
        # Sanitize relative directory components
        parts = [p for p in Path(relative_path).parts if p not in ("..", "/", "\\", ".", "")]
        if len(parts) > 1:
            subdirs = parts[:-1]
            target_dir = save_dir.joinpath(*subdirs)
            target_dir.mkdir(parents=True, exist_ok=True)
            target_path = target_dir / clean_name
        else:
            target_path = save_dir / clean_name
    else:
        target_path = save_dir / clean_name

    print(f"\n[+] Incoming File: '{clean_name}'")
    print(f"    Size: {format_bytes(filesize)} ({filesize:,} bytes)")
    print(f"    Saving to: {target_path}")

    # 1. Check if complete file already exists with matching checksum
    if target_path.exists() and target_path.stat().st_size == filesize:
        if calculate_sha256(str(target_path)).lower() == expected_checksum.lower():
            print(f"[✔] File is already completely downloaded and verified: '{clean_name}'")
            send_packet(client_sock, {
                "status": "ALREADY_EXISTS",
                "offset": filesize,
                "saved_to": str(target_path.resolve()),
                "message": "File is already completely downloaded."
            })
            return True

    # 2. Check for partial .part file for resuming
    part_path = target_path.with_name(clean_name + ".part")
    offset = 0
    resumed = False

    if part_path.exists():
        part_size = part_path.stat().st_size
        if 0 < part_size < filesize:
            offset = part_size
            resumed = True
            percent = (offset / max(filesize, 1)) * 100.0
            print(f"[⚡] Found partial file: '{part_path.name}' ({format_bytes(offset)})")
            print(f"[⚡] Resuming download from offset: {format_bytes(offset)} ({percent:.1f}%)")
        elif part_size >= filesize:
            # Corrupted or oversized partial file - reset
            try:
                part_path.unlink()
            except Exception:
                pass

    # 3. Send acknowledgment ready packet with offset
    try:
        send_packet(client_sock, {
            "status": "READY",
            "offset": offset,
            "resumed": resumed,
            "message": "Ready to receive data."
        })
    except Exception as e:
        print(f"[!] Failed to send ready acknowledgment: {e}")
        return False

    # 4. Receive the file stream chunk by chunk (append if resuming)
    file_mode = "ab" if offset > 0 else "wb"
    bytes_received = offset
    progress = ProgressBar(filesize, title=f"Downloading {clean_name}", initial_bytes=offset)

    try:
        with open(part_path, file_mode) as f:
            while bytes_received < filesize:
                remaining = filesize - bytes_received
                to_read = min(CHUNK_SIZE, remaining)
                chunk = client_sock.recv(to_read)
                if not chunk:
                    raise ConnectionError("Connection was lost while receiving file stream.")
                
                f.write(chunk)
                bytes_received += len(chunk)
                progress.update(len(chunk))

        progress.finish("File download complete.")
    except Exception as e:
        sys.stdout.write("\n")
        print(f"[!] Error during file download: {e}")
        print(f"[*] Partial file preserved: '{part_path.name}' ({format_bytes(bytes_received)} / {format_bytes(filesize)}). Ready to resume later.")
        try:
            send_packet(client_sock, {"status": "ERROR", "message": str(e)})
        except Exception:
            pass
        return False

    # 5. Verify Full File SHA-256 Checksum
    print(f"[*] Verifying SHA-256 checksum...")
    calculated_checksum = calculate_sha256(str(part_path))
    checksum_match = (calculated_checksum.lower() == expected_checksum.lower())

    if checksum_match:
        # Move .part to target_path atomically
        if target_path.exists():
            try:
                target_path.unlink()
            except Exception:
                target_path = get_unique_filepath(target_path.parent, clean_name)
        part_path.replace(target_path)
        print(f"[✔] Integrity check passed! SHA-256 verified: {calculated_checksum[:16]}...")
        print(f"[📂] File saved to: {target_path.resolve()}")
        send_packet(client_sock, {
            "status": "SUCCESS",
            "checksum_match": True,
            "saved_to": str(target_path.resolve()),
            "received_checksum": calculated_checksum
        })
    else:
        print("[✖] Warning: Checksum MISMATCH!")
        print(f"    Expected:   {expected_checksum}")
        print(f"    Calculated: {calculated_checksum}")
        try:
            part_path.unlink()
        except Exception:
            pass
        send_packet(client_sock, {
            "status": "ERROR",
            "checksum_match": False,
            "message": "Checksum verification failed."
        })

    return True


def handle_client(client_sock: socket.socket, client_addr: tuple, save_dir: Path):
    """
    Handle an active incoming connection from a sender device.
    """
    print(f"\n=======================================================")
    print(f"[+] Connected to Sender at {client_addr[0]}:{client_addr[1]}")
    print(f"=======================================================")

    count = 0
    try:
        while True:
            continues = receive_single_file(client_sock, save_dir, client_addr)
            if not continues:
                break
            count += 1
    except Exception as e:
        print(f"[!] Connection error: {e}")
    finally:
        try:
            client_sock.close()
        except Exception:
            pass
        print(f"[*] Finished connection with {client_addr[0]}. Total files received: {count}")


def start_receiver(bind_host: str = "0.0.0.0", port: int = DEFAULT_PORT, save_dir: str = "received_files"):
    """
    Start receiver server loop with dual IPv4 and IPv6 support for seamless
    localhost tunnel (SSH/ngrok) forwarding on Windows.
    """
    save_path = Path(save_dir).resolve()
    save_path.mkdir(parents=True, exist_ok=True)

    listening_sockets = []

    # 1. Primary IPv4 socket
    try:
        s4 = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s4.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        s4.bind((bind_host, port))
        s4.listen(5)
        listening_sockets.append(s4)
    except Exception as e:
        print(f"[!] Warning: IPv4 bind on {bind_host}:{port} failed: {e}")

    # 2. IPv6 socket (for Windows OpenSSH localhost [::1] compatibility)
    if bind_host in ("0.0.0.0", "localhost", "127.0.0.1", ""):
        try:
            s6 = socket.socket(socket.AF_INET6, socket.SOCK_STREAM)
            s6.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            s6.bind(("::", port))
            s6.listen(5)
            listening_sockets.append(s6)
        except Exception:
            pass

    if not listening_sockets:
        print(f"[!] Fatal: Could not bind any socket to port {port}.")
        return

    print("=" * 60)
    print("           PYTHON SOCKET FILE RECEIVER (SERVER)           ")
    print("=" * 60)
    print(f"[*] Save Folder:  {save_path}")
    print(f"[*] Listening on: Port {port} (IPv4 + IPv6 localhost ready)")
    print("\n[+] To send files from another device, enter one of these IPs on the sender:")
    for ip in get_all_ips():
        print(f"    👉  {ip}:{port}")
    print("=" * 60)
    print("[*] Waiting for incoming connections... (Press Ctrl+C to stop)\n")

    try:
        while True:
            readable, _, _ = select.select(listening_sockets, [], [], 1.0)
            for s in readable:
                client_sock, client_addr = s.accept()
                handle_client(client_sock, client_addr, save_path)
                print("\n[*] Ready for next file transfer...")
    except KeyboardInterrupt:
        print("\n[*] Receiver stopped by user.")
    finally:
        for s in listening_sockets:
            try:
                s.close()
            except Exception:
                pass


def main():
    parser = argparse.ArgumentParser(description="Python Socket File Transfer - Receiver")
    parser.add_argument("--port", "-p", type=int, default=DEFAULT_PORT, help=f"Port to listen on (default: {DEFAULT_PORT})")
    parser.add_argument("--bind", "-b", type=str, default="0.0.0.0", help="Host/IP to bind (default: 0.0.0.0)")
    parser.add_argument("--save-dir", "-d", type=str, default="received_files", help="Directory where received files will be saved")
    
    args = parser.parse_args()
    start_receiver(bind_host=args.bind, port=args.port, save_dir=args.save_dir)


if __name__ == "__main__":
    main()

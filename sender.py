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
        status = ack.get("status")
        if status == "ALREADY_EXISTS":
            print(f"[✔] File is already completely transferred on receiver! Skipping upload: '{filename}'\n")
            return True
        elif status != "READY":
            print(f"[!] Receiver rejected transfer: {ack.get('message')}")
            return False
    except Exception as e:
        print(f"[!] Did not receive ready acknowledgment from receiver: {e}")
        return False

    offset = ack.get("offset", 0)
    if offset > 0:
        percent = (offset / max(filesize, 1)) * 100.0
        print(f"[⚡] Resuming upload from offset: {format_bytes(offset)} ({percent:.1f}%)")

    # 3. Stream file chunks (seeking to offset if resuming)
    progress = ProgressBar(filesize, title=f"Uploading {filename}", initial_bytes=offset)
    bytes_sent = offset

    try:
        with open(file_path, "rb") as f:
            if offset > 0:
                f.seek(offset)
            while bytes_sent < filesize:
                remaining = filesize - bytes_sent
                to_read = min(CHUNK_SIZE, remaining)
                chunk = f.read(to_read)
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
    except socket.gaierror as e:
        print(f"\n[!] DNS Address Resolution Error ({e}):")
        print(f"    Cannot find or resolve host: '{host}'")
        print("    ---------------------------------------------------------")
        print("    Possible causes:")
        print("    1. The Pinggy / ngrok URL has expired or was regenerated on the receiver.")
        print("    2. Check for typos in the address or port.")
        print("    3. Check your internet connection.")
        print("    ---------------------------------------------------------\n")
        return
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
    - tcp://xyz.run.pinggy-free.link:36523
    - "0.tcp.in.ngrok.io:10744"
    - 192.168.1.15:5001
    - 192.168.1.15
    """
    host_str = host_str.strip().strip('"').strip("'").strip()
    # Strip protocols if user pasted from ngrok, pinggy, etc.
    for proto in ("tcp://", "http://", "https://", "ssh://"):
        if host_str.lower().startswith(proto):
            host_str = host_str[len(proto):]
            break

    # Strip any trailing slashes or URL paths
    host_str = host_str.rstrip("/")
    if "/" in host_str:
        host_str = host_str.split("/")[0]

    if ":" in host_str:
        parts = host_str.rsplit(":", 1)
        host = parts[0].strip()
        try:
            port = int(parts[1].strip())
            return host, port
        except ValueError:
            return host, default_port
    return host_str.strip(), None


def interactive_mode():
    """
    Interactive terminal prompt for entering receiver IP and files.
    Allows sending multiple files consecutively without closing.
    """
    print("=" * 60)
    print("            PYTHON SOCKET FILE SENDER (CLIENT)            ")
    print("=" * 60)

    # 1. Receiver Host
    default_host = "127.0.0.1"
    host_input = input(
        f"Enter Receiver IP / ngrok / Pinggy URL [e.g. 0.tcp.in.ngrok.io:10744 or press Enter for {default_host}]: "
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

    print(f"\n[*] Connecting to receiver at {host}:{port}...")
    try:
        sock = socket.create_connection((host, port), timeout=30)
        sock.settimeout(None)
        print("[+] Connected successfully!\n")
    except socket.gaierror as e:
        print(f"\n[!] DNS Address Resolution Error ({e}):")
        print(f"    Cannot find or resolve host: '{host}'")
        print("    ---------------------------------------------------------")
        print("    Possible causes:")
        print("    1. The Pinggy / ngrok URL has expired or was regenerated on the receiver.")
        print("    2. Check for typos in the address or port.")
        print("    3. Check your internet connection.")
        print("    ---------------------------------------------------------\n")
        return
    except socket.timeout:
        print(f"[!] Connection timed out trying to reach {host}:{port}.")
        print("    Please verify receiver is running and tunnel/port is correct.")
        return
    except Exception as e:
        print(f"[!] Could not connect to {host}:{port} - {e}")
        return

    transferred_total = 0
    try:
        while True:
            # 3. File or Folder Path
            while True:
                target_path_input = input("Enter path to file or folder to send (or drag & drop here) [or 'q' to quit]: ").strip()
                if target_path_input.lower() in ("q", "quit", "exit"):
                    try:
                        send_packet(sock, {"action": "SESSION_END"})
                    except Exception:
                        pass
                    return
                cleaned_path = clean_input_path(target_path_input)
                if not cleaned_path:
                    print("[!] Path cannot be empty.\n")
                    continue
                
                target_path = Path(cleaned_path).resolve()
                if not target_path.exists():
                    print(f"[!] '{target_path}' not found! Please check path.\n")
                    continue
                break

            if target_path.is_dir():
                transferred_total += send_folder(sock, target_path)
            elif target_path.is_file():
                if send_file(sock, target_path):
                    transferred_total += 1

            # Ask user if they want to send another file
            print("=" * 60)
            print(f"[✔] Total file(s) transferred so far: {transferred_total}")
            print("=" * 60)
            again = input("Do you want to send another file/folder? (y/n) [Default: y]: ").strip().lower()
            if again in ("n", "no", "q", "exit"):
                break
            print()

        # Send session end packet to notify receiver
        try:
            send_packet(sock, {"action": "SESSION_END"})
        except Exception:
            pass

    except (ConnectionError, BrokenPipeError, socket.error) as e:
        print(f"\n[!] Connection lost with receiver: {e}")
    finally:
        try:
            sock.close()
        except Exception:
            pass

    print(f"\n[✔] Session finished. Total files sent: {transferred_total}")


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
    try:
        main()
    except KeyboardInterrupt:
        print("\n\nOperation cancelled by user.")
    except Exception as e:
        print(f"\n[!] Unexpected error: {e}")
    finally:
        # Prevent console window from auto-closing on Windows when double-clicked
        if len(sys.argv) == 1:
            try:
                input("\nPress Enter to exit...")
            except Exception:
                pass

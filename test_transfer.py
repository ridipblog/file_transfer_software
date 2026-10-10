"""
test_transfer.py - Automated test for Python Socket File Transfer
Tests sending and receiving single files, binary files, and folders over socket.
"""

import os
import sys
import time
import shutil
import socket
import threading
from pathlib import Path

# Add current directory to path
sys.path.insert(0, str(Path(__file__).parent))

from protocol import calculate_sha256
import receiver
import sender

TEST_PORT = 5055
TEST_SEND_DIR = Path("test_send_data")
TEST_RECV_DIR = Path("test_recv_data")


def setup_test_files():
    if TEST_SEND_DIR.exists():
        shutil.rmtree(TEST_SEND_DIR)
    if TEST_RECV_DIR.exists():
        shutil.rmtree(TEST_RECV_DIR)

    TEST_SEND_DIR.mkdir(parents=True, exist_ok=True)
    TEST_RECV_DIR.mkdir(parents=True, exist_ok=True)

    # 1. Plain text file
    file1 = TEST_SEND_DIR / "sample.txt"
    file1.write_text("Hello from Device A! Socket file transfer test content.\n" * 100, encoding="utf-8")

    # 2. Binary file with random-like bytes (256 KB)
    file2 = TEST_SEND_DIR / "binary_data.dat"
    file2.write_bytes(os.urandom(256 * 1024))

    # 3. Subfolder with nested files
    nested_dir = TEST_SEND_DIR / "subfolder"
    nested_dir.mkdir(parents=True, exist_ok=True)
    nested_file = nested_dir / "nested_doc.txt"
    nested_file.write_text("Nested document inside subfolder.\n" * 50, encoding="utf-8")

    return file1, file2, nested_dir


def run_test_server(server_ready_event, stop_event):
    server_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server_sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    server_sock.bind(("127.0.0.1", TEST_PORT))
    server_sock.listen(1)
    server_sock.settimeout(1.0)
    server_ready_event.set()

    while not stop_event.is_set():
        try:
            client_sock, client_addr = server_sock.accept()
            receiver.handle_client(client_sock, client_addr, TEST_RECV_DIR)
            break
        except socket.timeout:
            continue
        except Exception as e:
            print("Server exception:", e)
            break
    server_sock.close()


def run_all_tests():
    print("[*] Setting up test files...")
    file1, file2, nested_dir = setup_test_files()
    orig_f1_hash = calculate_sha256(str(file1))
    orig_f2_hash = calculate_sha256(str(file2))
    orig_nested_hash = calculate_sha256(str(nested_dir / "nested_doc.txt"))

    server_ready = threading.Event()
    stop_event = threading.Event()
    server_thread = threading.Thread(target=run_test_server, args=(server_ready, stop_event), daemon=True)
    server_thread.start()

    server_ready.wait(timeout=5)
    time.sleep(0.5)

    print("\n[*] Running client sender to transfer test files...")
    sender.run_sender(
        host="127.0.0.1",
        port=TEST_PORT,
        items_to_send=[str(file1), str(file2), str(nested_dir)]
    )

    stop_event.set()
    server_thread.join(timeout=3)

    print("\n" + "=" * 50)
    print("           VERIFYING RECEIVED FILES")
    print("=" * 50)

    # Verify file 1
    recv_f1 = TEST_RECV_DIR / "sample.txt"
    assert recv_f1.exists(), f"Missing {recv_f1}"
    assert calculate_sha256(str(recv_f1)) == orig_f1_hash, "Checksum mismatch for sample.txt"
    print(" [✔] sample.txt: PASS (Size and Checksum match)")

    # Verify file 2
    recv_f2 = TEST_RECV_DIR / "binary_data.dat"
    assert recv_f2.exists(), f"Missing {recv_f2}"
    assert calculate_sha256(str(recv_f2)) == orig_f2_hash, "Checksum mismatch for binary_data.dat"
    print(" [✔] binary_data.dat (256 KB): PASS (Size and Checksum match)")

    # Verify nested folder file
    recv_nested = TEST_RECV_DIR / "subfolder" / "nested_doc.txt"
    assert recv_nested.exists(), f"Missing {recv_nested}"
    assert calculate_sha256(str(recv_nested)) == orig_nested_hash, "Checksum mismatch for nested file"
    print(" [✔] subfolder/nested_doc.txt: PASS (Relative path preserved, Checksum match)")

    print("\n[🎉] ALL TESTS PASSED SUCCESSFULLY!")

    # Cleanup test dirs
    shutil.rmtree(TEST_SEND_DIR, ignore_errors=True)
    shutil.rmtree(TEST_RECV_DIR, ignore_errors=True)
    print("[*] Cleaned up temporary test artifacts.")


if __name__ == "__main__":
    run_all_tests()

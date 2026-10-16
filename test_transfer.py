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

    print("\n[🎉] Standard Transfer Tests Passed!")

    # Test Resuming
    test_resumable_transfer()

    # Cleanup test dirs
    shutil.rmtree(TEST_SEND_DIR, ignore_errors=True)
    shutil.rmtree(TEST_RECV_DIR, ignore_errors=True)
    print("\n[🎉] ALL TESTS (INCLUDING RESUME) PASSED SUCCESSFULLY!")
    print("[*] Cleaned up temporary test artifacts.")


def test_resumable_transfer():
    print("\n" + "=" * 50)
    print("      TESTING INTERRUPTED & RESUMABLE TRANSFER")
    print("=" * 50)

    from protocol import send_packet, recv_packet

    resume_send = TEST_SEND_DIR / "large_resume_file.bin"
    test_data = os.urandom(512 * 1024)  # 512 KB
    resume_send.write_bytes(test_data)
    expected_hash = calculate_sha256(str(resume_send))
    filesize = len(test_data)
    half_size = filesize // 2

    # 1. Start server for session 1
    server_ready = threading.Event()
    stop_event = threading.Event()
    server_thread = threading.Thread(target=run_test_server, args=(server_ready, stop_event), daemon=True)
    server_thread.start()
    server_ready.wait(timeout=5)
    time.sleep(0.2)

    # 2. Simulate client sending only 50% (256 KB) and then abruptly closing socket!
    print(f"[*] Simulating client sending 50% ({half_size} bytes) and disconnecting...")
    s1 = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s1.connect(("127.0.0.1", TEST_PORT))
    send_packet(s1, {
        "action": "TRANSFER_FILE",
        "filename": "large_resume_file.bin",
        "filesize": filesize,
        "checksum": expected_hash,
        "relative_path": ""
    })
    ack1 = recv_packet(s1)
    assert ack1.get("status") == "READY", f"Expected READY, got {ack1}"
    assert ack1.get("offset") == 0

    # Send only first 256 KB
    s1.sendall(test_data[:half_size])
    time.sleep(0.3)
    # Abruptly close socket (simulate system shutdown / crash)
    s1.close()

    stop_event.set()
    server_thread.join(timeout=3)

    # Verify that .part file was preserved on receiver disk
    part_file = TEST_RECV_DIR / "large_resume_file.bin.part"
    assert part_file.exists(), "Expected .part file to be preserved after disconnect!"
    part_size = part_file.stat().st_size
    assert part_size >= half_size, f"Expected at least {half_size} bytes in .part file, got {part_size}"
    print(f" [✔] Partial .part file preserved: {part_size} bytes ({part_size/filesize*100:.1f}%)")

    # 3. Start server for session 2 (reconnection)
    print("\n[*] Reconnecting to RESUME remaining 50%...")
    server_ready2 = threading.Event()
    stop_event2 = threading.Event()
    server_thread2 = threading.Thread(target=run_test_server, args=(server_ready2, stop_event2), daemon=True)
    server_thread2.start()
    server_ready2.wait(timeout=5)
    time.sleep(0.2)

    # Use standard sender.run_sender to resume
    sender.run_sender(
        host="127.0.0.1",
        port=TEST_PORT,
        items_to_send=[str(resume_send)]
    )

    stop_event2.set()
    server_thread2.join(timeout=3)

    # Verify that .part file was completed and renamed to large_resume_file.bin
    final_file = TEST_RECV_DIR / "large_resume_file.bin"
    assert final_file.exists(), f"Final file {final_file} missing!"
    assert not part_file.exists(), "Temporary .part file was not cleaned up!"
    actual_hash = calculate_sha256(str(final_file))
    assert actual_hash == expected_hash, f"Hash mismatch after resume! Expected {expected_hash}, got {actual_hash}"
    print(f" [✔] RESUMABLE TRANSFER TEST: PASS (Resumed from 50%, 100% verified!)")


if __name__ == "__main__":
    run_all_tests()

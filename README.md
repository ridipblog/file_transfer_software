# Python Socket File Transfer Application

A high-performance, robust peer-to-peer file transfer application built with pure Python using TCP sockets. It allows you to transfer files and complete directory folders from one device to another device over a local network (Wi-Fi / Ethernet LAN) or VPN.

---

## 🌟 Key Features

- **Zero External Dependencies**: Built entirely with Python's standard library (`socket`, `struct`, `hashlib`, `json`, `pathlib`). No `pip install` required.
- **Data Integrity with SHA-256**: Automatically calculates cryptographic SHA-256 hashes on both ends to verify 100% corruption-free delivery.
- **Live Terminal Progress Bar**: Displays real-time progress bar `[██████░░░░]`, percentage, transferred bytes, transfer speed (MB/s), and ETA.
- **Single Files & Entire Folders**: Supports sending individual files or recursive folders while preserving subfolder structure.
- **Cross-Platform**: Works smoothly across Windows, Linux, macOS, and Android (Termux).
- **Auto IP Discovery**: The receiver automatically prints its local IP addresses so you know what IP to enter on the sender device.
- **Safe Path Handling**: Sanitizes filenames to prevent directory traversal and automatically renames duplicates to prevent accidental overwrites.
- **Unified Menu & Windows Double-Click Scripts**: Run `app.py` or double-click `.bat` scripts on Windows.

---

## 📂 Project Structure

```
c:\python_software\rat\
│── protocol.py         # Framing, packet serialization, SHA-256, and progress bar
│── receiver.py         # Server application (listens and saves incoming files)
│── sender.py           # Client application (connects to receiver and uploads files)
│── app.py              # Interactive console launcher (menu for Send / Receive)
│── run_app.bat         # Double-click launcher for Windows
│── run_receiver.bat    # Quick-launch receiver on Windows
│── run_sender.bat      # Quick-launch sender on Windows
│── test_transfer.py    # Automated end-to-end integration test
└── README.md           # Documentation and user guide
```

---

## 🚀 How to Transfer Files Between Two Devices

### Step 1: Make Sure Both Devices Are on the Same Network
Ensure Device A (Receiver) and Device B (Sender) are connected to the same Wi-Fi router, Ethernet switch, mobile hotspot, or VPN (e.g. Tailscale).

---

### Step 2: Start Receiver on Device A (Destination Device)

#### Option A: Quick Double-Click (Windows)
Double-click `run_receiver.bat` or `run_app.bat` and select `[1] RECEIVE Files`.

#### Option B: Terminal Command
```bash
py receiver.py
```
*(or `python receiver.py`)*

The receiver will print:
```
============================================================
           PYTHON SOCKET FILE RECEIVER (SERVER)           
============================================================
[*] Save Folder:  C:\python_software\rat\received_files
[*] Listening on: Port 5001

[+] To send files from another device, enter one of these IPs on the sender:
    👉  192.168.1.15:5001
============================================================
[*] Waiting for incoming connections... (Press Ctrl+C to stop)
```

Note the IP address shown (e.g. `192.168.1.15`).

---

### Step 3: Start Sender on Device B (Source Device)

#### Option A: Interactive Mode (Prompt / Drag-and-Drop)
Run:
```bash
py sender.py
```
Follow the interactive prompts:
1. Enter Receiver IP address: `192.168.1.15`
2. Enter Port: `5001` (or press Enter)
3. Enter path to file or folder (you can drag and drop any file directly into the terminal window)

#### Option B: Command Line (Fast / Scriptable)
```bash
# Send a single file:
py sender.py --host 192.168.1.15 --file "C:\Users\hp\Desktop\video.mp4"

# Send multiple files at once:
py sender.py --host 192.168.1.15 --file "report.pdf" --file "data.xlsx"

# Send an entire folder:
py sender.py --host 192.168.1.15 --file "C:\MyFolder"
```

---

## 🖥️ Receiver Options

| Option | Description | Default |
|---|---|---|
| `--port`, `-p` | Port number to listen on | `5001` |
| `--bind`, `-b` | Network interface to bind | `0.0.0.0` (all interfaces) |
| `--save-dir`, `-d` | Destination directory for incoming files | `received_files` |

Example:
```bash
py receiver.py --port 8080 --save-dir "D:\Downloads"
```

---

## 🛡️ Windows Firewall Notice

When running `receiver.py` for the first time, Windows Defender Firewall may display a pop-up asking for network permissions.
- Make sure to check **Private networks** (and Public networks if on hotspot/public Wi-Fi) and click **Allow access**.
- If connection times out from another device, ensure port `5001` is not blocked by your firewall.

---

## 🧪 Running Automated Tests

To test the socket transmission mechanism on your local machine:
```bash
py test_transfer.py
```
This runs an internal loopback test transferring text files, 256 KB binary payloads, and nested folder structures, verifying all SHA-256 hashes.

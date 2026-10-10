"""
app.py - Unified Launcher for Socket File Transfer Application
Run this file on either device to Send or Receive files with a single click.
"""

import sys
import os
from pathlib import Path

# Ensure current directory is in sys.path
sys.path.insert(0, str(Path(__file__).parent))

from protocol import get_all_ips, DEFAULT_PORT
import receiver
import sender


def show_my_ips():
    print("\n" + "=" * 50)
    print("           YOUR DEVICE IP ADDRESSES")
    print("=" * 50)
    ips = get_all_ips()
    for ip in ips:
        print(f"  • {ip}")
    print("=" * 50)
    print("Share one of these IPs with the sender device on your network.")
    input("\nPress Enter to return to main menu...")


def main_menu():
    while True:
        os.system("cls" if os.name == "nt" else "clear")
        print("=" * 55)
        print("     PYTHON SOCKET FILE TRANSFER APPLICATION (RAT)     ")
        print("=" * 55)
        print(" [1] 📥 RECEIVE Files (Start Receiver / Server)")
        print(" [2] 📤 SEND Files (Connect to Receiver & Send)")
        print(" [3] 🌐 Show My Device Network IP Addresses")
        print(" [4] ❌ Exit")
        print("=" * 55)

        choice = input("Enter choice (1-4): ").strip()

        if choice == "1":
            print("\nStarting Receiver...")
            port_input = input(f"Enter port to listen on [Press Enter for default {DEFAULT_PORT}]: ").strip()
            port = int(port_input) if port_input.isdigit() else DEFAULT_PORT
            save_dir_input = input("Enter folder to save files [Press Enter for 'received_files']: ").strip()
            save_dir = save_dir_input if save_dir_input else "received_files"
            receiver.start_receiver(port=port, save_dir=save_dir)
            input("\nPress Enter to return to main menu...")

        elif choice == "2":
            sender.interactive_mode()
            input("\nPress Enter to return to main menu...")

        elif choice == "3":
            show_my_ips()

        elif choice == "4" or choice.lower() in ("exit", "q"):
            print("\nExiting. Goodbye!")
            sys.exit(0)

        else:
            print("[!] Invalid option. Please enter 1, 2, 3, or 4.")
            input("Press Enter to continue...")


if __name__ == "__main__":
    try:
        main_menu()
    except KeyboardInterrupt:
        print("\n\nApplication interrupted. Goodbye!")
        sys.exit(0)

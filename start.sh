#!/usr/bin/env bash
cd "$(dirname "$0")"
command -v python3 >/dev/null || { echo "Python 3 is required."; exit 1; }
python3 -c "import websockets" 2>/dev/null || {
  echo "Missing 'websockets'. Install it with one of:"
  echo "  Arch:          sudo pacman -S python-websockets"
  echo "  Debian/Ubuntu: sudo apt install python3-websockets"
  echo "  Fedora:        sudo dnf install python3-websockets"
  exit 1
}
exec python3 bridge.py

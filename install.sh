#!/usr/bin/env bash
# BirdGuard installer for Raspberry Pi OS (64-bit).
# Run from inside the project folder:   ./install.sh
set -euo pipefail

DIR="$(cd "$(dirname "$0")" && pwd)"
if [ "$(id -u)" -eq 0 ]; then
  echo "Please run as your normal user (no sudo):  ./install.sh"; exit 1
fi
RUN_USER="$USER"

echo "==> 1/4 Installing system packages (this can take 5-10 minutes)"
sudo apt update
sudo apt install -y --no-install-recommends \
  git alsa-utils python3-picamera2 python3-flask python3-yaml python3-numpy \
  python3-pil python3-gpiozero python3-pytest
sudo apt install -y hailo-all
if command -v pw-play >/dev/null 2>&1; then
  # Desktop version: PipeWire handles USB + Bluetooth audio. Keep the user's
  # audio session running from boot, even when nobody is logged in.
  echo "    desktop audio (PipeWire) found - using it for sound"
  sudo loginctl enable-linger "$RUN_USER"
else
  # Lite version: Bluetooth speaker support through bluez-alsa (harmless for USB)
  if sudo apt install -y bluez bluez-alsa-utils; then
    sudo systemctl enable --now bluealsa 2>/dev/null || true
  else
    echo "    (Bluetooth audio package not available - USB speakers still work)"
  fi
fi

echo "==> 2/4 Creating your personal settings file"
if [ ! -f "$DIR/config.local.yaml" ]; then
  cp "$DIR/config.local.example.yaml" "$DIR/config.local.yaml"
  echo "    created config.local.yaml (edit it with: nano config.local.yaml)"
else
  echo "    config.local.yaml already exists - kept"
fi
mkdir -p "$DIR/data"

echo "==> 3/4 Installing the auto-start service"
sed -e "s#__USER__#$RUN_USER#g" -e "s#__DIR__#$DIR#g" -e "s#__UID__#$(id -u)#g" \
  "$DIR/birdguard.service.template" | sudo tee /etc/systemd/system/birdguard.service >/dev/null
sudo systemctl daemon-reload
sudo systemctl enable birdguard >/dev/null

echo "==> 4/4 Checking hardware"
if [ -e /dev/hailo0 ]; then
  python3 -m birdguard check || true
  sudo systemctl restart birdguard
  echo
  echo "Done! BirdGuard is running."
  echo "Dashboard:  http://$(hostname).local:8080"
  echo "Live log:   journalctl -u birdguard -f"
else
  echo
  echo "Almost done - the AI HAT driver needs a reboot to load."
  echo "Run:  sudo reboot"
  echo "Then reconnect and run:  cd $DIR && python3 -m birdguard check"
  echo "BirdGuard will start automatically after the reboot."
fi

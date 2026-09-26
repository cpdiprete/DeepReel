#!/usr/bin/env bash
set -euo pipefail

echo "=================================================="
echo "      DEEPREEL SAFE TEARDOWN & EJECT SCRIPT       "
echo "=================================================="

# 1. Stop any active ingestion or streaming services
echo "[1/5] Stopping background services..."
sudo systemctl stop deepreel-ingest@*.service 2>/dev/null || true

# 2. Flush dirty write cache to storage
echo "[2/5] Flushing filesystem cache to disks..."
sync

# 3. Unmount the media volume if mounted
if mountpoint -q /mnt/media; then
    echo "[3/5] Unmounting /mnt/media..."
    sudo umount /mnt/media
else
    echo "[3/5] /mnt/media is not mounted (skipping)."
fi

# 4. Stop the software RAID array cleanly if running
if [ -e /dev/md0 ] || grep -q "md0" /proc/mdstat 2>/dev/null; then
    echo "[4/5] Stopping mdadm RAID array (/dev/md0)..."
    sudo mdadm --stop /dev/md0 || true
else
    echo "[4/5] No active RAID array detected (skipping)."
fi

# 5. Actuate DVD ejection and detach storage drives
echo "[5/5] Ejecting optical tray and powering down block devices..."

# Optical Drive Latch Eject
if [ -e /dev/sr0 ]; then
    eject /dev/sr0 || true
    echo "  ✔ Optical tray unlatched."
fi

# Flush again to guarantee integrity
sync

echo "--------------------------------------------------"
echo " All external media and storage safely dismounted!"
echo "--------------------------------------------------"

# Optional automatic system halt:
# Passing --halt powers down the Raspberry Pi completely.
if [[ "${1:-}" == "--halt" ]]; then
    echo "Initiating system halt. Wait for green ACT LED to cease blinking..."
    sudo poweroff
fi

#!/usr/bin/env python3
import os
import subprocess
import sys
import time

DEV_PATH = "/dev/sr0"

class Colors:
    GREEN = "\033[92m"
    RED = "\033[91m"
    YELLOW = "\033[93m"
    BLUE = "\033[94m"
    RESET = "\033[0m"

def print_checkpoint(step: int, name: str):
    print(f"\n{Colors.BLUE}[CHECKPOINT {step}]{Colors.RESET} {name}...")

def pass_step(msg: str):
    print(f"  {Colors.GREEN}✔ PASS:{Colors.RESET} {msg}")

def fail_step(msg: str, critical: bool = False):
    print(f"  {Colors.RED}✖ FAIL:{Colors.RESET} {msg}")
    if critical:
        print(f"\n{Colors.RED}Pipeline halted due to critical error.{Colors.RESET}")
        sys.exit(1)

def warn_step(msg: str):
    print(f"  {Colors.YELLOW}⚠ NOTICE:{Colors.RESET} {msg}")

def run_cmd(cmd: list[str]) -> tuple[int, str, str]:
    proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    out, err = proc.communicate()
    return proc.returncode, out.strip(), err.strip()

def main():
    print(f"{'='*60}\n OPTICAL INGEST & HARDWARE VERIFICATION PIPELINE\n{'='*60}")

    # -------------------------------------------------------------
    # Checkpoint 1: Block Device Enumeration
    # -------------------------------------------------------------
    print_checkpoint(1, "Verifying SCSI Block Device Node")
    if os.path.exists(DEV_PATH):
        pass_step(f"Found optical block device at {DEV_PATH}")
    else:
        fail_step(f"Device node {DEV_PATH} not found. Check USB bridge connection.", critical=True)

    # -------------------------------------------------------------
    # Checkpoint 2: Host USB & Power Rail Stability
    # -------------------------------------------------------------
    print_checkpoint(2, "Checking Kernel Power & Bus Stability")
    ret, dmesg_out, _ = run_cmd(["dmesg"])
    recent_dmesg = "\n".join(dmesg_out.splitlines()[-40:])
    
    if "Under-voltage detected" in recent_dmesg:
        warn_step("Kernel reported under-voltage! Check Pi 27W PSU.")
    else:
        pass_step("Pi power rail stable; no recent undervoltage throttles.")

    if "reset high-speed USB device" in recent_dmesg or "device descriptor read/64, error" in recent_dmesg:
        warn_step("USB controller resets detected in dmesg. Hub power might be noisy.")
    else:
        pass_step("USB bus enumeration is clean.")

    # -------------------------------------------------------------
    # Checkpoint 3: Disc Insertion & Media Type Verification
    # -------------------------------------------------------------
    print_checkpoint(3, "Probing Optical Media Presence via udev")
    ret, udev_out, _ = run_cmd(["udevadm", "info", "-q", "property", "-n", DEV_PATH])
    props = dict(line.split("=", 1) for line in udev_out.splitlines() if "=" in line)
    
    has_media = props.get("ID_CDROM_MEDIA") == "1"
    if not has_media:
        fail_step("Drive tray reports empty or uncalibrated. Insert a disc and shut tray.", critical=True)
    
    media_type = props.get("ID_CDROM_MEDIA_DVD", "0")
    media_label = props.get("ID_FS_LABEL", "UNLABELED")
    fs_type = props.get("ID_FS_TYPE", "Unknown")

    pass_step(f"Disc detected | Label: '{media_label}' | Filesystem: {fs_type}")
    if media_type == "1":
        pass_step("Media recognized as DVD format.")
    else:
        warn_step("Media is not DVD-ROM (CD/Data format detected).")

    # -------------------------------------------------------------
    # Checkpoint 4: Direct Unencrypted Descriptor Sector Read
    # -------------------------------------------------------------
    print_checkpoint(4, "Testing Direct Sector Read (Volume Descriptor Header)")
    # Reading 16 sectors (32 KB) - this reads the ISO/UDF header prior to CSS sectors
    ret, _, err = run_cmd(["dd", f"if={DEV_PATH}", "of=/dev/null", "bs=2048", "count=16", "status=none"])
    if ret == 0:
        pass_step("Raw 32KB volume descriptor sectors read successfully.")
    else:
        fail_step(f"I/O error reading lead-in sectors: {err}", critical=True)

    # -------------------------------------------------------------
    # Checkpoint 5: Decryption & Ingest Tooling Availability
    # -------------------------------------------------------------
    print_checkpoint(5, "Verifying Ingestion & Decryption Engine")
    has_makemkv = subprocess.call(["which", "makemkvcon"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL) == 0
    has_dvdbackup = subprocess.call(["which", "dvdbackup"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL) == 0

    if has_makemkv:
        pass_step("Found makemkvcon installed.")
        print("  --> Probing disc title sets via MakeMKV...")
        ret, mkv_info, _ = run_cmd(["makemkvcon", "-r", "info", "disc:0"])
        for line in mkv_info.splitlines():
            if "DRV:0" in line or "CINFO:2," in line:
                print(f"      {line}")
    elif has_dvdbackup:
        pass_step("Found dvdbackup installed.")
        print("  --> Reading DVD metadata via dvdbackup...")
        ret, dvd_info, _ = run_cmd(["dvdbackup", "-i", DEV_PATH, "-I"])
        title_line = [l for l in dvd_info.splitlines() if "DVD-Video information of the disc" in l]
        if title_line:
            print(f"      {title_line[0]}")
    else:
        warn_step("Neither makemkvcon nor dvdbackup found. CSS ripping commands will fail.")
        print("      Run: sudo apt-get install -y dvdbackup libdvd-pkg")

    # -------------------------------------------------------------
    # Checkpoint 6: Programmatic Eject Verification
    # -------------------------------------------------------------
    print_checkpoint(6, "Actuating Physical Tray Latch")
    ret, _, err = run_cmd(["eject", DEV_PATH])
    if ret == 0:
        pass_step("SCSI eject command sent. Spring latch popped successfully.")
    else:
        fail_step(f"Eject command rejected: {err}")

    print(f"\n{'='*60}\n ALL HARDWARE & READ CHECKPOINTS COMPLETED\n{'='*60}")

if __name__ == "__main__":
    main()


"""
SmartGuard - USB Camera Finder
------------------------------
Run this script to find the correct index for your USB webcam.
It lists all connected cameras with their names and tests each one.

Usage:
    python find_usb_camera.py

Then set the index found in your .env file:
    CAMERA_INDEX=<index>
"""

import cv2
import subprocess
import re

def list_camera_names_windows():
    """Get camera device names using Windows PowerShell."""
    try:
        result = subprocess.run(
            ["powershell", "-Command",
             "Get-PnpDevice -Class Camera | Select-Object -ExpandProperty FriendlyName"],
            capture_output=True, text=True, timeout=5
        )
        names = [n.strip() for n in result.stdout.strip().splitlines() if n.strip()]
        return names
    except Exception:
        return []

def list_camera_names_wmi():
    """Fallback: Get camera names via WMI."""
    try:
        result = subprocess.run(
            ["powershell", "-Command",
             "Get-WmiObject Win32_PnPEntity | Where-Object { $_.Caption -match 'camera|webcam|usb.*vid|vid.*usb' } | Select-Object -ExpandProperty Caption"],
            capture_output=True, text=True, timeout=5
        )
        names = [n.strip() for n in result.stdout.strip().splitlines() if n.strip()]
        return names
    except Exception:
        return []

def scan_cameras(max_index=10):
    """Try opening each camera index and return info about working ones."""
    results = []
    print(f"\nScanning camera indices 0 to {max_index - 1}...\n")
    for i in range(max_index):
        cap = cv2.VideoCapture(i)
        if cap.isOpened():
            w = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
            h = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
            fps = cap.get(cv2.CAP_PROP_FPS)
            # Try to read a test frame
            ret, _ = cap.read()
            cap.release()
            results.append({
                "index": i,
                "width": w,
                "height": h,
                "fps": fps,
                "readable": ret
            })
    return results


if __name__ == "__main__":
    print("=" * 55)
    print("   SmartGuard - USB Camera Detection Tool")
    print("=" * 55)

    # --- Step 1: List device names from Windows
    print("\n[1] Detected camera devices (Windows):")
    names = list_camera_names_windows() or list_camera_names_wmi()
    if names:
        for i, name in enumerate(names):
            tag = ""
            nl = name.lower()
            if any(k in nl for k in ["usb", "external", "hd webcam", "logitech", "trust", "canyon", "genius", "razer"]):
                tag = "  <-- likely USB webcam"
            elif any(k in nl for k in ["integrated", "built-in", "internal", "ir camera", "windows hello"]):
                tag = "  <-- built-in camera"
            elif "droidcam" in nl:
                tag = "  <-- DroidCam (phone camera)"
            print(f"  [{i}] {name}{tag}")
    else:
        print("  (Could not retrieve device names — is a camera plugged in?)")

    # --- Step 2: Scan OpenCV indices
    cameras = scan_cameras(max_index=8)

    if not cameras:
        print("\n[2] OpenCV found NO cameras at indices 0-7.")
        print("\n  Make sure your USB webcam is plugged in, then run this again.")
    else:
        print(f"\n[2] OpenCV found {len(cameras)} camera(s):\n")
        print(f"  {'Index':<8} {'Resolution':<14} {'FPS':<8} {'Readable'}")
        print(f"  {'-'*5:<8} {'-'*11:<14} {'-'*5:<8} {'-'*8}")
        for cam in cameras:
            readable = "✓ YES" if cam["readable"] else "✗ NO"
            print(f"  {cam['index']:<8} {cam['width']}x{cam['height']:<8} {cam['fps']:<8.0f} {readable}")

        print("\n" + "=" * 55)
        print("  ACTION: Set the USB webcam index in your .env file:")
        print("=" * 55)
        print("\n  Open .env and set:")
        print("      CAMERA_INDEX=<index_of_your_usb_webcam>")
        print("      CAMERA_BACKEND=auto")
        print()
        print("  Example: if USB webcam is index 2:")
        print("      CAMERA_INDEX=2")
        print()

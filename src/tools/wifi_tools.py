# src/tools/wifi_tools.py
import subprocess
import time
import os
from pathlib import Path

_last_scan = []   # holds SSID list after scan


# -----------------------------
# Helper to run commands
# -----------------------------
def run(cmd, suppress_errors=True):
    import subprocess
    try:
        out = subprocess.check_output(cmd, shell=True, stderr=subprocess.STDOUT, text=True)
        return out.strip()
    except subprocess.CalledProcessError as e:
        return "" if suppress_errors else (e.output or "")


# -----------------------------
# Enable Wi-Fi adapter
# -----------------------------
def wifi_on():
    run('netsh interface set interface name="Wi-Fi" admin=enabled')
    time.sleep(1)
    return "Wi-Fi enabled."


# -----------------------------
# Disconnect Wi-Fi (safer than disabling)
# -----------------------------
def wifi_off():
    run("netsh wlan disconnect")
    return "Wi-Fi turned OFF."


# -----------------------------
# Scan Wi-Fi networks
# Also populates _last_scan[]
# -----------------------------
def list_wifi():
    global _last_scan
    _last_scan = []

    for _ in range(5):
        result = run("netsh wlan show networks mode=bssid", suppress_errors=False)

        if "location" in result.lower() or "administrator" in result.lower():
            subprocess.Popen('powershell -command "Start-Process ms-settings:privacy-location"', shell=True)
            return "Windows requires Location Services to be enabled in order to scan for Wi-Fi routers! I have opened the settings page for you. Please turn it on and try again!"

        if "SSID" not in result:
            time.sleep(0.7)
            continue
        
        ssids = []
        for line in result.splitlines():
            line = line.strip()
            if line.startswith("SSID "):
                name = line.split(":", 1)[1].strip()
                if name:
                    ssids.append(name)

        _last_scan = ssids
        if ssids:
            break
        time.sleep(0.7)

    if not _last_scan:
        return f"Unable to scan Wi-Fi networks. Windows reported: {result}"

    out = ["Available Wi-Fi Networks:"]
    for i, ssid in enumerate(_last_scan, 1):
        out.append(f"{i}. {ssid}")

    return "\n".join(out)


# -----------------------------
# Create Wi-Fi XML profile
# -----------------------------
def _generate_wifi_profile_xml(ssid, password):
    # Open network (no password)
    if password is None or password.strip() == "":
        return f"""
        <WLANProfile xmlns="http://www.microsoft.com/networking/WLAN/profile/v1">
            <name>{ssid}</name>
            <SSIDConfig>
                <SSID>
                    <name>{ssid}</name>
                </SSID>
            </SSIDConfig>
            <connectionType>ESS</connectionType>
            <connectionMode>manual</connectionMode>
            <MSM>
                <security>
                    <authAlgorithm>open</authAlgorithm>
                    <encryption>none</encryption>
                </security>
            </MSM>
        </WLANProfile>
        """

    # WPA2 PSK Network
    return f"""
    <WLANProfile xmlns="http://www.microsoft.com/networking/WLAN/profile/v1">
        <name>{ssid}</name>
        <SSIDConfig>
            <SSID>
                <name>{ssid}</name>
            </SSID>
        </SSIDConfig>
        <connectionType>ESS</connectionType>
        <connectionMode>manual</connectionMode>
        <MSM>
            <security>
                <authEncryption>
                    <authentication>WPA2PSK</authentication>
                    <encryption>AES</encryption>
                    <useOneX>false</useOneX>
                </authEncryption>
                <sharedKey>
                    <keyType>passPhrase</keyType>
                    <protected>false</protected>
                    <keyMaterial>{password}</keyMaterial>
                </sharedKey>
            </security>
        </MSM>
    </WLANProfile>
    """


# -----------------------------
# Connect by selecting Wi-Fi number
# -----------------------------
def connect_wifi_by_number(n: int, password: str = None) -> str:
    global _last_scan

    if not _last_scan:
        return "Please say 'list Wi-Fi' first."

    if n < 1 or n > len(_last_scan):
        return "Invalid Wi-Fi number."

    ssid = _last_scan[n - 1]

    # Dynamically ask for password if not provided
    if password is None:
        import tkinter as tk
        from tkinter import simpledialog
        try:
            root = tk.Tk()
            root.withdraw()
            root.attributes("-topmost", True)
            password = simpledialog.askstring("Wi-Fi Password", 
                                            f"Enter password for '{ssid}'\n(Leave blank if already saved or open network):",
                                            parent=root, show='*')
            root.destroy()
        except Exception:
            password = ""
            
    if not password:
        # Try direct connect (assumes saved profile or Open network)
        conn_result = run(f'netsh wlan connect name="{ssid}" ssid="{ssid}"')
        if "completed successfully" in conn_result.lower():
            return f"Connected to {ssid}."
        return f"Failed to connect to {ssid}. If it is a new network, please try again and provide a password."

    # Save XML profile
    xml_data = _generate_wifi_profile_xml(ssid, password)
    profile_path = Path(os.getenv("LOCALAPPDATA")) / "TorqueAI" / f"{ssid}.xml"
    profile_path.parent.mkdir(parents=True, exist_ok=True)
    profile_path.write_text(xml_data, encoding="utf-8")

    # Add profile
    add_result = run(f'netsh wlan add profile filename="{profile_path}" user=all')
    if "error" in add_result.lower():
        return f"Failed to add Wi-Fi profile for {ssid}."

    # Connect
    conn_result = run(f'netsh wlan connect name="{ssid}" ssid="{ssid}"')

    # Check result
    if "completed successfully" in conn_result.lower():
        return f"Connected to {ssid}."

    return f"Failed to connect to {ssid}. Check password or try again."


def register(router, tool_map):
    router.add_intent("wifi_on", ["turn on wifi", "enable wifi", "wifi on"], lambda _t: wifi_on())
    router.add_intent("wifi_off", ["turn off wifi", "disable wifi", "wifi off"], lambda _t: wifi_off())
    router.add_intent("wifi_list", ["list wifi", "scan wifi", "show wifi", "wifi networks", "list out the wifi"], lambda _t: list_wifi())
    router.add_intent("wifi_connect", ["connect to wifi", "connect wifi", "connect to network"], lambda _t: "")

    tool_map.update({
        "wifi_on": wifi_on, "wifi_off": wifi_off,
        "list_wifi": list_wifi, "connect_wifi": connect_wifi_by_number
    })

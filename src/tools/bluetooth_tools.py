import subprocess

def run(cmd):
    try:
        out = subprocess.check_output(["powershell", "-Command", cmd], text=True, stderr=subprocess.STDOUT)
        return out.strip()
    except subprocess.CalledProcessError:
        return ""

def bluetooth_on(_: str = "") -> str:
    """Toggles the Windows Bluetooth radio service ON."""
    run("If ((Get-Service bthserv).Status -eq 'Stopped') { Start-Service bthserv }")
    return "Bluetooth enabled. Make sure your hardware switch is on."

def bluetooth_off(_: str = "") -> str:
    """Toggles the Windows Bluetooth radio service OFF."""
    run("If ((Get-Service bthserv).Status -eq 'Running') { Stop-Service bthserv -Force }")
    return "Bluetooth disabled."

_last_scan_bt = []

def list_bluetooth(_: str = "") -> str:
    """Retrieves all paired Bluetooth hardware via PnpDevice."""
    global _last_scan_bt
    res = run('Get-PnpDevice -Class Bluetooth | Where-Object { $_.Present -eq $true } | Select-Object -ExpandProperty FriendlyName')
    if not res:
        return "No active Bluetooth hardware found or Bluetooth is currently OFF."
    
    # Filter out redundant windows adapters
    _last_scan_bt = [line.strip() for line in res.splitlines() if line.strip() and not line.strip().startswith("Microsoft Bluetooth")]
    
    if not _last_scan_bt:
        return "No discoverable devices found."
        
    out = ["Found Bluetooth Devices:"]
    for i, dev in enumerate(_last_scan_bt, 1):
        out.append(f"{i}. {dev}")
    return "\n".join(out)

def connect_bluetooth(user_text: str = "") -> str:
    """Forwards the user to the Windows Settings page due to strict CLI pairing limitations."""
    subprocess.Popen('powershell -command "Start-Process ms-settings:bluetooth"', shell=True)
    return "I have opened your Bluetooth settings. Due to Windows security, please click 'Connect' to finalize the pairing."


def register(router, tool_map):
    router.add_intent("bluetooth_on", ["turn on bluetooth", "enable bluetooth", "start bluetooth"], bluetooth_on)
    router.add_intent("bluetooth_off", ["turn off bluetooth", "disable bluetooth", "stop bluetooth"], bluetooth_off)
    router.add_intent("list_bluetooth", ["list bluetooth devices", "show bluetooth", "scan for bluetooth", "available bluetooth"], list_bluetooth)
    router.add_intent("connect_bluetooth", ["connect to bluetooth", "pair bluetooth", "connect bluetooth speaker"], connect_bluetooth)

    tool_map.update({
        "bluetooth_on": bluetooth_on, "bluetooth_off": bluetooth_off,
        "list_bluetooth": list_bluetooth, "connect_bluetooth": connect_bluetooth
    })

